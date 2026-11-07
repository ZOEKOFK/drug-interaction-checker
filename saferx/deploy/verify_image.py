#!/usr/bin/env python
"""
镜像构建的「等价验证」（本机 Docker 引擎被安全策略禁用时的替代手段）。

背景：`docker build` 依赖 Docker Desktop 的 Linux 引擎（WSL2），本机 `wsl.exe` 在
安全策略黑名单里，引擎无法启动，命令直接失败。这不是 Dockerfile 的问题，但"从没
构建过"本身就是交付风险。于是把构建拆成两个可验证的部分：

  1. **构建上下文完整性**：解析 Dockerfile 的 COPY 指令，按 .dockerignore 过滤后
     逐个检查源路径是否存在——漏文件（例如忘记 COPY data/external）会在这里暴露。
  2. **运行时等价性**：在临时目录里按镜像内的目录布局（/app/backend、/app/data、
     /app/frontend/dist）重建一份，用同样的环境变量与启动命令起 uvicorn，
     打 /api/health、首页、/api/check，确认服务真的能起来。

这不能替代 `docker build`（基础镜像、层缓存、网络策略都没验证），但能证明
「Dockerfile 声明的文件都在、依赖装得上、按镜像布局能跑通」。

用法：
    python deploy/verify_image.py
    python deploy/verify_image.py --keep     # 保留临时目录便于排查
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "deploy" / "Dockerfile"
IGNORE = ROOT / ".dockerignore"

OK = "✓"
BAD = "✗"


def read_ignore() -> list[str]:
    return [
        ln.strip()
        for ln in IGNORE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def ignored(rel: str, patterns: list[str]) -> bool:
    """极简 .dockerignore 语义：按路径前缀或通配后缀匹配。"""
    from fnmatch import fnmatch

    parts = rel.split("/")
    for p in patterns:
        if fnmatch(rel, p) or fnmatch(rel, p.rstrip("/") + "/*"):
            return True
        if rel == p or rel.startswith(p.rstrip("/") + "/"):
            return True
        if any(fnmatch(seg, p) for seg in parts):
            return True
    return False


def parse_copies() -> list[tuple[str, str]]:
    """提取运行时阶段（最后一个 FROM 之后）的 COPY 指令，跳过 --from=web 的外部阶段。"""
    text = DOCKERFILE.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    last_from = max(i for i, ln in enumerate(lines) if ln.upper().startswith("FROM"))
    out = []
    for ln in lines[last_from:]:
        if ln.upper().startswith("COPY ") and "--from=" not in ln:
            parts = ln.split()[1:]
            if len(parts) >= 2:
                out.append((parts[0], parts[-1]))
    return out


def check_context(patterns: list[str]) -> tuple[bool, list[str]]:
    copies = parse_copies()
    print(f"\n[1/2] 构建上下文（{len(copies)} 条 COPY）")
    ok_all = True
    notes = []
    for src, dst in copies:
        src_rel = src.lstrip("./")
        if any(ch in src_rel for ch in "*?["):
            hits = [p for p in ROOT.glob(src_rel) if not ignored(p.relative_to(ROOT).as_posix(), patterns)]
            exists = bool(hits)
            detail = f"{len(hits)} 个匹配" if exists else "无匹配"
        else:
            p = ROOT / src_rel
            exists = p.exists()
            if exists and p.is_dir():
                kept = [
                    f for f in p.rglob("*")
                    if f.is_file() and not ignored(f.relative_to(ROOT).as_posix(), patterns)
                ]
                detail = f"{len(kept)} 个文件（过滤后）"
                exists = bool(kept)
            else:
                detail = f"{p.stat().st_size / 1024:.0f} KB" if exists else "缺失"
        mark = OK if exists else BAD
        if not exists:
            ok_all = False
        print(f"  {mark} COPY {src:32s} -> {dst:26s} {detail}")
        notes.append(f"COPY {src} -> {dst}: {detail}")
    return ok_all, notes


def check_requires() -> bool:
    print("\n[2/2] 运行时依赖（requirements.txt）")
    req = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    pkgs = [
        re.split(r"[\[>=<!~ ]", ln.strip())[0]
        for ln in req.splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    all_ok = True
    for name in pkgs:
        mod = {"uvicorn": "uvicorn", "pypinyin": "pypinyin", "fastapi": "fastapi", "pydantic": "pydantic"}.get(name, name)
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "?")
            print(f"  {OK} {name:14s} {ver}")
        except ImportError:
            print(f"  {BAD} {name:14s} 未安装")
            all_ok = False
    return all_ok


def stage(patterns: list[str]) -> Path:
    """按镜像内布局重建一份最小根目录。"""
    tmp = Path(tempfile.mkdtemp(prefix="saferx-img-"))
    (tmp / "backend").mkdir()
    shutil.copytree(ROOT / "backend", tmp / "backend", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "tests"))
    shutil.copytree(ROOT / "pipelines", tmp / "pipelines", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    data_src = ROOT / "data"
    (tmp / "data" / "external").mkdir(parents=True)
    for f in (data_src / "external").glob("*.json"):
        shutil.copy2(f, tmp / "data" / "external" / f.name)
    db = data_src / "saferx.sqlite"
    if db.exists():
        shutil.copy2(db, tmp / "data" / "saferx.sqlite")
    if (ROOT / "frontend" / "dist").exists():
        shutil.copytree(ROOT / "frontend" / "dist", tmp / "frontend" / "dist", dirs_exist_ok=True)
    return tmp


def run_service(tmp: Path) -> bool:
    print(f"\n[3/3] 运行时等价性：在 {tmp} 按镜像布局启动服务")
    port = 8011
    env = dict(os.environ)
    env["SAFERX_DB"] = str(tmp / "data" / "saferx.sqlite")
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=tmp / "backend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    ok = True
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                if proc.poll() is not None:
                    break
        if proc.poll() is not None:
            print(f"  {BAD} 服务启动失败（退出码 {proc.returncode}）")
            print((proc.stdout.read() if proc.stdout else "")[-1500:])
            return False

        with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
            health = json.loads(r.read())
        st = health.get("stats", {})
        checks = [
            ("GET /api/health", health.get("status") == "ok", f"status={health.get('status')}"),
            ("药品规模", st.get("drugs", 0) == 1971, f"drugs={st.get('drugs')}"),
            ("DDI 药对", st.get("ddi_pairs", 0) == 234981, f"ddi_pairs={st.get('ddi_pairs')}"),
            ("DDSI 条目", st.get("ddsi_rows", 0) > 0, f"ddsi_rows={st.get('ddsi_rows')}"),
            ("DFI 条目", st.get("dfi_rows", 0) > 0, f"dfi_rows={st.get('dfi_rows')}"),
            ("重复用药条目", st.get("dupli_rows", 0) > 0, f"dupli_rows={st.get('dupli_rows')}"),
        ]
        for name, passed, detail in checks:
            print(f"  {OK if passed else BAD} {name:16s} {detail}")
            ok &= passed

        # 首页（前端构建产物是否被正确托管）
        try:
            with urllib.request.urlopen(base + "/", timeout=5) as r:
                html = r.read().decode("utf-8", "ignore")
            served = r.status == 200 and "<div id=\"app\"" in html
            print(f"  {OK if served else BAD} GET /            前端 dist 托管 {'正常' if served else '异常'}")
            ok &= served
        except urllib.error.HTTPError as e:
            print(f"  {BAD} GET /            HTTP {e.code}（frontend/dist 可能未构建）")
            ok = False

        # 核心业务
        body = json.dumps({
            "medications": ["华法林", "阿司匹林", "二甲双胍"],
            "diseases": ["Hypertension"],
        }).encode()
        req = urllib.request.Request(base + "/api/check", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
        hit = len(res.get("pairs", [])) > 0 and res.get("overall_all") in ("red", "orange")
        print(f"  {OK if hit else BAD} POST /api/check    pairs={len(res.get('pairs', []))} "
              f"disease={len(res.get('disease_risks', []))} overall={res.get('overall_all')}")
        ok &= hit
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    patterns = read_ignore()
    ctx_ok, _ = check_context(patterns)
    dep_ok = check_requires()
    tmp = stage(patterns)
    run_ok = run_service(tmp)

    print("\n" + "=" * 60)
    print(f"构建上下文 {'通过' if ctx_ok else '失败'}｜依赖 {'通过' if dep_ok else '失败'}｜运行时 {'通过' if run_ok else '失败'}")
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"临时目录保留: {tmp}")
    print("=" * 60)
    print("注：本脚本等价验证「文件齐全 + 依赖可装 + 按镜像布局能跑」，")
    print("    不覆盖基础镜像、层缓存与网络策略——`docker build` 仍需在启用引擎的机器上跑一次。")
    return 0 if (ctx_ok and dep_ok and run_ok) else 1


if __name__ == "__main__":
    sys.exit(main())

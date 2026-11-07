#!/usr/bin/env python
"""
生成「发布专用」的最小目录（deploy/site/）。

为什么不直接发布仓库根目录：
  * ml/models 有 424MB 预训练权重、frontend/node_modules 有数百 MB，上传会超时；
  * 很多托管平台会把 frontend/dist 当构建产物剔除，导致首页 404；
  * data/raw 里是 500MB 原始 CSV，运行时完全用不到。

所以这里按「运行时真正需要什么」重新组织一份：
    site/
      backend/            FastAPI 应用（去掉 tests/__pycache__）
      pipelines/          数据管道（仅在数据库缺失时用到）
      data/external/      人工审编 JSON
      data/saferx.sqlite  已构建好的数据库（45MB，随包发布）
      web/                前端构建产物（原 frontend/dist，改名避开 build-output 规则）
      requirements.txt

用法：
    python deploy/prepare_site.py
    PORT=8080 sh deploy/site/start.sh     # 本地模拟线上启动
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "deploy" / "site"


def copytree(src: Path, dst: Path, ignore_patterns=("__pycache__", "*.pyc", ".pytest_cache", "tests")):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*ignore_patterns))


def _prune_stale_assets(web: Path) -> int:
    """删除 web/assets 下没被引用的旧构建产物，返回删除数量。

    Vite 产物带内容 hash，每次构建都换名字；dirs_exist_ok 覆盖复制不会清除旧的，
    累积下来会把发布包撑大几十个无用文件。

    注意引用有两种形态，都必须跟：
      1) index.html 里写绝对路径   /assets/index-xxx.js
      2) chunk 之间互相动态 import 写相对路径  "./AboutView-xxx.js"
    只认第一种会把动态路由的 chunk 当垃圾删掉（实测曾删掉 AboutView），
    用户点「关于」才 404。
    """
    entry = web / "index.html"
    if not entry.is_file():
        return 0
    assets = web / "assets"
    # 匹配任意带 hash 的文件名，再回到 assets/ 下确认存在——两种引用形态一次覆盖
    name_re = re.compile(r"([A-Za-z0-9_.\-]+\.(?:js|css|svg|png|jpe?g|webp|woff2?|ttf))")

    keep, queue = set(), [entry]
    while queue:
        path = queue.pop()
        if path in keep:
            continue
        keep.add(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in name_re.finditer(text):
            candidate = assets / match.group(1)
            if candidate.is_file() and candidate not in keep:
                queue.append(candidate)

    removed = 0
    for path in assets.rglob("*"):
        if path.is_file() and path not in keep:
            path.unlink()
            removed += 1
    return removed


def main() -> int:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("前端未构建：先运行 cd frontend && npm run build", file=sys.stderr)
        return 1
    if not (ROOT / "data" / "saferx.sqlite").exists():
        print("数据库不存在：先运行 make initdb", file=sys.stderr)
        return 1

    # 默认不整目录删除（rmtree 会被安全策略拦），改为覆盖复制；
    # 需要彻底重建时显式传 --clean，由调用方自行确认。
    if SITE.exists():
        if "--clean" in sys.argv:
            shutil.rmtree(SITE)
        else:
            print("· 发布目录已存在，覆盖更新（要彻底重建请加 --clean）")
    SITE.mkdir(parents=True, exist_ok=True)

    copytree(ROOT / "backend", SITE / "backend")
    copytree(ROOT / "pipelines", SITE / "pipelines", ignore_patterns=("__pycache__", "*.pyc"))
    (SITE / "data" / "external").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "data" / "external").glob("*.json"):
        shutil.copy2(f, SITE / "data" / "external" / f.name)
    shutil.copy2(ROOT / "data" / "saferx.sqlite", SITE / "data" / "saferx.sqlite")
    shutil.copytree(ROOT / "frontend" / "dist", SITE / "web", dirs_exist_ok=True)
    shutil.copy2(ROOT / "backend" / "requirements.txt", SITE / "requirements.txt")

    # dist 每次构建都会换 hash 文件名，覆盖复制会把历史产物全留着（实测累积到三套）。
    # 从 index.html 出发做引用闭包，删掉没被任何入口引用到的旧 chunk。
    pruned = _prune_stale_assets(SITE / "web")
    if pruned:
        print(f"· 清理 {pruned} 个陈旧前端产物")

    (SITE / "start.sh").write_text(
        "#!/usr/bin/env sh\n"
        "# 线上启动：托管平台注入 PORT，服务需绑 0.0.0.0\n"
        "set -e\n"
        'cd "$(dirname "$0")/backend"\n'
        'exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"\n',
        encoding="utf-8",
        newline="\n",  # 必须 LF：CRLF 会让 Linux 的 sh 报 "set: Illegal option -"
    )

    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    n = sum(1 for f in SITE.rglob("*") if f.is_file())
    print(f"✓ 发布目录 {SITE}")
    print(f"  {n} 个文件，{total / 1024 / 1024:.1f} MB")
    for p in sorted(SITE.iterdir()):
        kind = "dir " if p.is_dir() else "file"
        print(f"  {kind} {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

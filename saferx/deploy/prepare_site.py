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

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "deploy" / "site"


def copytree(src: Path, dst: Path, ignore_patterns=("__pycache__", "*.pyc", ".pytest_cache", "tests")):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*ignore_patterns))


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

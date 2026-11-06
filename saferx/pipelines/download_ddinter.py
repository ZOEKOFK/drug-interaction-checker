#!/usr/bin/env python
"""
下载 DDInter 2.0 官方按分类 CSV -> data/raw/

官方下载页 https://ddinter2.scbdd.com/download/ 页面仅列出 8 个链接，
但按 URL 规则实际存在 14 个分类文件（ATC 首字母 A-G, H, J, L-N, P, R, S, V）。

用法: python pipelines/download_ddinter.py [--force]
"""
import argparse
import sys
import time
from pathlib import Path
import urllib.request

BASE_URL = "https://ddinter2.scbdd.com/static/media/download/ddinter_downloads_code_{}.csv"
CODES = list("ABCDEFGHJKLMNPRSV")  # 14 个分类

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def download(code: str, force: bool = False) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / f"ddinter_code_{code}.csv"
    if dest.exists() and not force and dest.stat().st_size > 1000:
        print(f"  [skip] {dest.name} 已存在（{dest.stat().st_size // 1024} KB）")
        return dest
    url = BASE_URL.format(code)
    for attempt in range(1, 4):
        try:
            print(f"  [get ] {url} (第 {attempt} 次)")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SafeRx-pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            dest.write_bytes(data)
            print(f"  [done] {dest.name}: {len(data) // 1024} KB")
            return dest
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 失败: {e}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"下载失败: {code}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="强制重新下载")
    args = parser.parse_args()

    print(f"== 下载 DDInter 2.0 分类 CSV 到 {RAW_DIR} ==")
    total = 0
    for code in CODES:
        download(code, force=args.force)
        total += 1
    print(f"== 完成：{total} 个文件 ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())

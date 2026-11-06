#!/usr/bin/env python
"""
抓取 DDInter 2.0 的「其他相互作用」三类数据（官方未提供 CSV，仅有网页表格接口）：
  - DDSI  药物-疾病禁忌  /server/disease-interaction-source/   约 8,359 条
  - DFI   药物-食物相互作用 /server/food-interaction-source/     约   857 条
  - 重复用药              /server/dupli-interaction-source/      约 6,033 条

接口是 Django + DataTables(serverSide)，需要：
  1) 先 GET /server/other_interaction/ 建立会话并取 csrfmiddlewaretoken
  2) 再按 start/length 分页 POST（实测 length=500 可用）

产物（不入库，见 .gitignore）：data/raw/other_interactions/*.jsonl
        快照元信息：data/raw/other_interactions/_snapshot.json

用法：
  python pipelines/download_other_interactions.py            # 抓取（有缓存时可用 --force 覆盖）
  python pipelines/download_other_interactions.py --offline  # 仅校验本地缓存
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "other_interactions"

BASE = "https://ddinter2.scbdd.com"
BOOTSTRAP = f"{BASE}/server/other_interaction/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SafeRx-coursework/1.0"
)
PAGE_SIZE = 500
SLEEP = 0.6  # 限速：礼貌抓取，避免对公共服务造成压力

# 名称 -> (接口路径, 参考总条数[仅用于估算页数，实际以接口 recordsTotal 为准])
TARGETS = {
    "disease": ("/server/disease-interaction-source/", 8359),
    "food": ("/server/food-interaction-source/", 857),
    "dupli": ("/server/dupli-interaction-source/", 6033),
}


def build_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def bootstrap(opener) -> tuple[str, str]:
    """建立会话，返回 (csrfmiddlewaretoken, cookie 概要)。"""
    req = urllib.request.Request(BOOTSTRAP, headers={"User-Agent": UA})
    with opener.open(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")
    m = re.search(r"csrfmiddlewaretoken:\s*'([^']+)'", html)
    if not m:
        m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    if not m:
        raise RuntimeError("未能从页面解析 csrfmiddlewaretoken（页面结构可能已变更）")
    return m.group(1), "session established"


def post_page(opener, token: str, path: str, start: int, length: int) -> dict:
    body = urllib.parse.urlencode(
        {"draw": 1, "start": start, "length": length, "csrfmiddlewaretoken": token}
    ).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-CSRFToken": token,
            "Referer": BOOTSTRAP,
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    with opener.open(req, timeout=60) as resp:
        payload = resp.read().decode("utf-8", "ignore")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"接口返回非 JSON（{path} start={start}）：{payload[:200]}") from exc


def fetch_one(opener, token: str, name: str, path: str, force: bool) -> int:
    out = RAW_DIR / f"{name}.jsonl"
    if out.exists() and not force and out.stat().st_size > 0:
        n = sum(1 for _ in out.open(encoding="utf-8"))
        print(f"  {name:8} 已存在（{n} 行），跳过；--force 可重新抓取")
        return n

    first = post_page(opener, token, path, 0, PAGE_SIZE)
    total = int(first.get("recordsTotal") or 0)
    if total == 0:
        raise RuntimeError(f"{name}: 接口返回 0 条，可能是会话或参数失效")

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    print(f"  {name:8} 共 {total} 条 / {pages} 页", end="", flush=True)

    rows = list(first.get("data") or [])
    for p in range(1, pages):
        time.sleep(SLEEP)
        resp = post_page(opener, token, path, p * PAGE_SIZE, PAGE_SIZE)
        rows.extend(resp.get("data") or [])
        print(".", end="", flush=True)

    # 去重（以 id 为准，重复用药表无 id 则用全字段指纹）
    seen, uniq = set(), []
    for r in rows:
        key = r.get("id", json.dumps(r, sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    tmp = out.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in uniq:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(out)
    print(f" 完成 → {len(uniq)} 条（去重 {len(rows) - len(uniq)}）")
    return len(uniq)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="不联网，仅校验缓存")
    ap.add_argument("--force", action="store_true", help="覆盖已有缓存")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = RAW_DIR / "_snapshot.json"

    if args.offline:
        ok = True
        for name in TARGETS:
            p = RAW_DIR / f"{name}.jsonl"
            n = sum(1 for _ in p.open(encoding="utf-8")) if p.exists() else 0
            print(f"  {name:8} {n:6} 行  {'✓' if n else '✗ 缺失'}")
            ok &= n > 0
        return 0 if ok else 1

    print("建立会话 …")
    opener, _ = build_opener()
    token, _ = bootstrap(opener)
    print(f"csrf token: {token[:12]}…")

    counts = {}
    for name, (path, _expect) in TARGETS.items():
        counts[name] = fetch_one(opener, token, name, path, args.force)

    snapshot = {
        "source": "DDInter 2.0 (https://ddinter2.scbdd.com/server/other_interaction/)",
        "license": "CC BY-NC-SA 4.0",
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoints": {k: v[0] for k, v in TARGETS.items()},
        "rows": counts,
        "note": "官方仅提供网页表格接口（无 CSV），本文件为抓取快照，供学术复现",
    }
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n快照已写入", snapshot_path)
    print("合计", sum(counts.values()), "条")
    return 0


if __name__ == "__main__":
    sys.exit(main())

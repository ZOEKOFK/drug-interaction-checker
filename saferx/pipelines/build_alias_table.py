#!/usr/bin/env python
"""
构建别名映射表 -> data/processed/alias.csv

别名来源：
1. 自动：每个药物的英文名 / 小写 / 无空格连字符变体（1971 种药全覆盖）
2. 人工审编：data/external/alias_curated.json（常见慢病药物的中文通用名、拼音首字母、同义词）

用法: python pipelines/build_alias_table.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC_DIR = ROOT / "data" / "processed"
CURATED = ROOT / "data" / "external" / "alias_curated.json"

try:  # 拼音首字母自动生成（仅构建期依赖，运行期无）
    from pypinyin import Style, lazy_pinyin
except ImportError:  # pragma: no cover - 缺依赖时退化为手工 pinyin 字段
    lazy_pinyin = None
    Style = None


def norm(s: str) -> str:
    return s.strip().lower()


def pinyin_initials(text: str) -> str:
    """中文名 -> 拼音首字母（如 华法林 -> hfl）。"""
    if not text or lazy_pinyin is None:
        return ""
    try:
        return "".join(p[0] for p in lazy_pinyin(text, style=Style.FIRST_LETTER, errors="ignore") if p)
    except Exception:  # noqa: BLE001 - 个别生僻字失败不影响主流程
        return ""


def main() -> int:
    with open(PROC_DIR / "drugs.csv", encoding="utf-8", newline="") as fh:
        drugs = {r["name_en"]: r["ddinter_id"] for r in csv.DictReader(fh)}

    alias_map: dict[str, tuple[str, str]] = {}  # alias -> (kind, ddinter_id)
    conflicts = []

    def add(alias: str, kind: str, ddinter_id: str):
        alias = alias.strip()
        if not alias:
            return
        if alias in alias_map and alias_map[alias][1] != ddinter_id:
            conflicts.append(alias)
            return
        alias_map[alias] = (kind, ddinter_id)

    # 1) 自动英文别名
    for name_en, did in drugs.items():
        add(name_en, "en", did)
        add(norm(name_en), "en", did)
        compact = norm(name_en).replace(" ", "").replace("-", "")
        if compact:
            add(compact, "en", did)

    # 2) 人工审编别名
    curated = json.loads(CURATED.read_text(encoding="utf-8")) if CURATED.exists() else []
    matched = 0
    for item in curated:
        name_en = item["name_en"]
        did = drugs.get(name_en)
        if not did:
            print(f"  [warn] curated 药名未在库中找到: {name_en}（跳过）")
            continue
        matched += 1
        add(item["name_cn"], "cn", did)
        add(norm(item["name_cn"]), "cn", did)
        # 拼音优先取人工审编值，缺失时由 pypinyin 自动生成首字母
        py = item.get("pinyin") or pinyin_initials(item["name_cn"])
        if py:
            add(py, "pinyin", did)
        for syn in item.get("synonyms", []):
            add(syn, "synonym", did)
            add(norm(syn), "synonym", did)

    with open(PROC_DIR / "alias.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["alias", "kind", "ddinter_id"])
        for alias in sorted(alias_map):
            kind, did = alias_map[alias]
            w.writerow([alias, kind, did])

    kinds = Counter = {}
    from collections import Counter as _C
    kinds = _C(k for k, _ in alias_map.values())
    print(f"药物数              : {len(drugs)}")
    print(f"curated 命中        : {matched}/{len(curated)}")
    print(f"别名总数            : {len(alias_map)}")
    print(f"按类型分布          : {dict(kinds)}")
    if conflicts:
        print(f"冲突别名(已跳过)    : {sorted(set(conflicts))[:20]}")
    print(f"输出                : {PROC_DIR / 'alias.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

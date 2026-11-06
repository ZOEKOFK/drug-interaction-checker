#!/usr/bin/env python
"""
清洗 DDInter 原始 CSV -> data/processed/

规则（与方案 §3.3 一致）：
1. 无序对规范化：强制 ddinter_id_a < ddinter_id_b（字典序）
2. 去重：同一药对跨文件重复出现，保留唯一记录
3. 分级聚合：同一药对取最高风险等级（Major > Moderate > Minor > Unknown，保守策略宁可高报）
4. 枚举校验：level 必须属于 {Major, Moderate, Minor, Unknown}

输出:
  data/processed/drugs.csv  (ddinter_id, name_en, atc_class)
  data/processed/ddi.csv    (ddinter_id_a, ddinter_id_b, level)

用法: python pipelines/clean_ddinter.py
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"

LEVEL_RANK = {"Major": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
VALID_LEVELS = set(LEVEL_RANK)

# 官方下载文件按「药名首字母」分组（非 ATC 分类），故本表不含 ATC 元数据；
# 药物类别仅由 data/external/alias_curated.json 人工审编提供。


def canonical(a: str, b: str) -> tuple:
    return (a, b) if a < b else (b, a)


def main() -> int:
    files = sorted(RAW_DIR.glob("ddinter_code_*.csv"))
    if not files:
        print("错误：data/raw/ 下没有原始 CSV，请先运行 download_ddinter.py")
        return 1

    raw_rows = 0
    dropped = 0
    best_level: dict[tuple, str] = {}
    drug_names: dict[str, str] = {}

    for f in files:
        code = f.stem.rsplit("_", 1)[-1]
        with open(f, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                raw_rows += 1
                ida, idb = r["DDInterID_A"].strip(), r["DDInterID_B"].strip()
                na, nb = r["Drug_A"].strip(), r["Drug_B"].strip()
                level = r["Level"].strip()
                if level not in VALID_LEVELS or not ida or not idb:
                    dropped += 1
                    continue
                drug_names.setdefault(ida, na)
                drug_names.setdefault(idb, nb)
                key = canonical(ida, idb)
                if key not in best_level or LEVEL_RANK[level] > LEVEL_RANK[best_level[key]]:
                    best_level[key] = level

    PROC_DIR.mkdir(parents=True, exist_ok=True)

    with open(PROC_DIR / "drugs.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ddinter_id", "name_en"])
        for did in sorted(drug_names):
            w.writerow([did, drug_names[did]])

    with open(PROC_DIR / "ddi.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ddinter_id_a", "ddinter_id_b", "level"])
        for (a, b) in sorted(best_level):
            w.writerow([a, b, best_level[(a, b)]])

    print(f"原始行数        : {raw_rows}")
    print(f"非法行(丢弃)    : {dropped}")
    print(f"唯一药物对      : {len(best_level)}")
    print(f"药物数          : {len(drug_names)}")
    print(f"聚合后分级分布  : {dict(Counter(best_level.values()))}")
    print(f"输出            : {PROC_DIR / 'drugs.csv'}, {PROC_DIR / 'ddi.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

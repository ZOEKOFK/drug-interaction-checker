#!/usr/bin/env python
"""
清洗「其他相互作用」三份数据：

  data/raw/other_interactions/{disease,food,dupli}.jsonl
    → data/processed/{ddsi,dfi,dupli}.csv

规则：
  1. 分级 3/2/1 → Major/Moderate/Minor（与 DDInter 前端 badge 一致）
  2. 仅保留主库 drug 表中存在的药物（1971 种），丢弃无法挂接的记录
  3. 疾病/食物/类别补中文名（data/external/other_cn.json），未覆盖则留空由前端回退英文
  4. DFI 的机制字段在源接口中被误命名为 magnesium（官方前端 bug），这里按语义改名

用法: python pipelines/clean_other_interactions.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "other_interactions"
PROC_DIR = ROOT / "data" / "processed"
EXT_DIR = ROOT / "data" / "external"

LEVEL_MAP = {"3": "Major", "2": "Moderate", "1": "Minor"}
MECH_CN = {
    "Absorption": "吸收",
    "Metabolism": "代谢",
    "Synergy": "协同作用",
    "Antagonism": "拮抗作用",
    "Excretion": "排泄",
    "Distribution": "分布",
    "Others": "其他",
}


def mech_cn(raw: str | None) -> str:
    """'Absorption Metabolism' -> '吸收 + 代谢'"""
    if not raw:
        return ""
    parts = [MECH_CN.get(p.strip(), p.strip()) for p in str(raw).split() if p.strip()]
    return " + ".join(parts)


def load_jsonl(name: str) -> list[dict]:
    path = RAW_DIR / f"{name}.jsonl"
    if not path.exists():
        raise SystemExit(f"缺少 {path}，请先运行 download_other_interactions.py")
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    # 主库药物（用于挂接与补中文名）
    with (PROC_DIR / "drugs.csv").open(encoding="utf-8", newline="") as fh:
        drugs = list(csv.DictReader(fh))
    known = {d["ddinter_id"]: d["name_en"] for d in drugs}

    cn = json.loads((EXT_DIR / "other_cn.json").read_text(encoding="utf-8"))
    cn_dis, cn_food, cn_type = cn["disease"], cn["food"], cn["drugtype"]

    # ---------------- DDSI ----------------
    raw = load_jsonl("disease")
    rows, dropped = [], 0
    for r in raw:
        did = r.get("internalID_a_id")
        if did not in known:
            dropped += 1
            continue
        lv = LEVEL_MAP.get(str(r.get("level")))
        if not lv:
            dropped += 1
            continue
        rows.append([
            did,
            known[did],
            r.get("drugName") or known[did],
            r.get("diseaseName", ""),
            cn_dis.get(r.get("diseaseName", ""), ""),
            lv,
            (r.get("text") or "").strip(),
            (r.get("references") or "").strip(),
        ])
    write_csv(
        PROC_DIR / "ddsi.csv",
        ["ddinter_id", "drug_name_en", "drug_name_raw", "disease_en", "disease_cn", "level", "description_en", "reference_text"],
        rows,
    )
    ddsi_stats = {
        "raw": len(raw),
        "kept": len(rows),
        "dropped": dropped,
        "levels": dict(Counter(r[5] for r in rows)),
        "diseases": len({r[3] for r in rows}),
        "cn_covered": sum(1 for r in rows if r[4]),
    }

    # ---------------- DFI ----------------
    raw = load_jsonl("food")
    rows, dropped = [], 0
    for r in raw:
        did = r.get("internalID_a_id")
        if did not in known:
            dropped += 1
            continue
        lv = LEVEL_MAP.get(str(r.get("level")))
        if not lv:
            dropped += 1
            continue
        food_en = r.get("foodName", "")
        rows.append([
            did,
            known[did],
            r.get("drugName") or known[did],
            food_en,
            cn_food.get(food_en, ""),
            lv,
            (r.get("newInteraction") or "").strip(),
            (r.get("newManagement") or "").strip(),
            (r.get("magnesium") or "").strip(),          # 官方字段名有误，实为 mechanism
            mech_cn(r.get("magnesium")),
            (r.get("references") or "").strip(),
        ])
    write_csv(
        PROC_DIR / "dfi.csv",
        ["ddinter_id", "drug_name_en", "drug_name_raw", "food_en", "food_cn", "level",
         "interaction_en", "management_en", "mechanism_en", "mechanism_cn", "reference_text"],
        rows,
    )
    dfi_stats = {
        "raw": len(raw),
        "kept": len(rows),
        "dropped": dropped,
        "levels": dict(Counter(r[5] for r in rows)),
        "foods": len({r[3] for r in rows}),
        "cn_covered": sum(1 for r in rows if r[4]),
    }

    # ---------------- 重复用药 ----------------
    raw = load_jsonl("dupli")
    rows, dropped, seen = [], 0, set()
    for r in raw:
        did = r.get("internalID_b_id")
        if did not in known:
            dropped += 1
            continue
        cat = (r.get("drugtype") or "").strip()
        key = (did, cat, r.get("drugmulti") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append([
            cat,
            cn_type.get(cat, ""),
            did,
            known[did],
            r.get("drugb") or known[did],
            (r.get("drugmulti_trade") or "").strip(),
            (r.get("drugmulti") or "").strip(),
            (r.get("warning") or "").strip(),
            (r.get("note") or "").strip(),
        ])
    write_csv(
        PROC_DIR / "dupli.csv",
        ["category_en", "category_cn", "ddinter_id", "drug_name_en", "drug_name_raw",
         "combo_trade_name", "combo_ingredients", "warning_en", "note_en"],
        rows,
    )
    dupli_stats = {
        "raw": len(raw),
        "kept": len(rows),
        "dropped": dropped,
        "dup_removed": len(raw) - dropped - len(rows),
        "categories": len({r[0] for r in rows}),
        "cn_covered": sum(1 for r in rows if r[1]),
    }

    # ---------------- 输出 ----------------
    def show(title: str, s: dict) -> None:
        print(f"{title}")
        print(f"  原始 {s['raw']:6} → 入库 {s['kept']:6}（丢弃 {s['dropped']}）")
        if "levels" in s:
            print(f"  分级分布 {s['levels']}")
        if "diseases" in s:
            print(f"  疾病种类 {s['diseases']}，中文覆盖 {s['cn_covered']}/{s['kept']}")
        if "foods" in s:
            print(f"  食物种类 {s['foods']}，中文覆盖 {s['cn_covered']}/{s['kept']}")
        if "categories" in s:
            print(f"  药品种类 {s['categories']}，中文覆盖 {s['cn_covered']}/{s['kept']}")
        if s.get("dup_removed"):
            print(f"  去重 {s['dup_removed']} 条")

    show("DDSI 药物-疾病", ddsi_stats)
    show("DFI 药物-食物", dfi_stats)
    show("重复用药", dupli_stats)

    meta = {"ddsi": ddsi_stats, "dfi": dfi_stats, "dupli": dupli_stats}
    (PROC_DIR / "other_interactions_stats.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n统计写入 {PROC_DIR / 'other_interactions_stats.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

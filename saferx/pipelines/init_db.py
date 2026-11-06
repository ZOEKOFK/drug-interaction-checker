#!/usr/bin/env python
"""
建库：data/processed/*.csv + data/external/*.json -> data/saferx.sqlite

表结构（方案 §4.2，level 扩展支持 Unknown——DDInter 官方分级之一）：
  drug / ddi / mechanism / alias / template / meta

用法: python pipelines/init_db.py
"""
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC_DIR = ROOT / "data" / "processed"
EXT_DIR = ROOT / "data" / "external"
DB_PATH = ROOT / "data" / "saferx.sqlite"

DDL = """
DROP TABLE IF EXISTS meta;
DROP TABLE IF EXISTS template;
DROP TABLE IF EXISTS alias;
DROP TABLE IF EXISTS ddi;
DROP TABLE IF EXISTS mechanism;
DROP TABLE IF EXISTS drug;

CREATE TABLE drug (
  ddinter_id  TEXT PRIMARY KEY,
  name_en     TEXT NOT NULL,
  name_cn     TEXT,
  atc_code    TEXT,
  atc_name    TEXT,
  category    TEXT
);
CREATE INDEX idx_drug_name_en ON drug(name_en);

CREATE TABLE mechanism (
  id             INTEGER PRIMARY KEY,
  text_en        TEXT NOT NULL,
  text_cn        TEXT NOT NULL,
  management_cn  TEXT NOT NULL
);

-- DDI 关系表（无序对规范化：强制 ddinter_id_a < ddinter_id_b）
CREATE TABLE ddi (
  id            INTEGER PRIMARY KEY,
  ddinter_id_a  TEXT NOT NULL REFERENCES drug(ddinter_id),
  ddinter_id_b  TEXT NOT NULL REFERENCES drug(ddinter_id),
  level         TEXT NOT NULL CHECK (level IN ('Major','Moderate','Minor','Unknown')),
  mechanism_id  INTEGER REFERENCES mechanism(id),
  source_id     TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_pair ON ddi(ddinter_id_a, ddinter_id_b);

-- 别名映射表（中文匹配的关键）
CREATE TABLE alias (
  alias       TEXT PRIMARY KEY,
  kind        TEXT CHECK (kind IN ('cn','en','pinyin','synonym')),
  ddinter_id  TEXT NOT NULL REFERENCES drug(ddinter_id)
);
CREATE INDEX idx_alias_id ON alias(ddinter_id);

-- 慢病模板药单表（答辩演示用）
CREATE TABLE template (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  desc_text  TEXT,
  expected   TEXT,
  drugs_json TEXT NOT NULL
);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
"""


def main() -> int:
    for required in ["drugs.csv", "ddi.csv", "alias.csv"]:
        if not (PROC_DIR / required).exists():
            print(f"错误：缺少 {PROC_DIR / required}，请先运行 clean_ddinter.py / build_alias_table.py")
            return 1

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)

    # ---- curated 数据 ----
    alias_curated = json.loads((EXT_DIR / "alias_curated.json").read_text(encoding="utf-8")) if (EXT_DIR / "alias_curated.json").exists() else []
    mech_curated = json.loads((EXT_DIR / "mechanism_curated.json").read_text(encoding="utf-8")) if (EXT_DIR / "mechanism_curated.json").exists() else []
    tpl_curated = json.loads((EXT_DIR / "templates_curated.json").read_text(encoding="utf-8")) if (EXT_DIR / "templates_curated.json").exists() else []

    # ---- 药物主表 ----
    with open(PROC_DIR / "drugs.csv", encoding="utf-8", newline="") as fh:
        drugs = list(csv.DictReader(fh))
    curated_by_en = {c["name_en"].lower(): c for c in alias_curated}
    conn.executemany(
        "INSERT INTO drug (ddinter_id, name_en, name_cn, atc_name, category) VALUES (?,?,?,?,?)",
        [
            (
                d["ddinter_id"], d["name_en"],
                curated_by_en.get(d["name_en"].lower(), {}).get("name_cn"),
                None,
                curated_by_en.get(d["name_en"].lower(), {}).get("category"),
            )
            for d in drugs
        ],
    )
    name2id = {d["name_en"]: d["ddinter_id"] for d in drugs}

    # ---- 机制表 + DDI 表 ----
    mech_index = {}  # (id_a, id_b) -> mechanism_id
    for i, m in enumerate(mech_curated, start=1):
        a, b = name2id.get(m["a"]), name2id.get(m["b"])
        if not a or not b:
            print(f"  [warn] 机制条目药名未命中: {m['a']} + {m['b']}")
            continue
        conn.execute(
            "INSERT INTO mechanism (id, text_en, text_cn, management_cn) VALUES (?,?,?,?)",
            (i, m["mechanism_en"], m["mechanism_cn"], m["management"]),
        )
        mech_index[tuple(sorted([a, b]))] = i

    with open(PROC_DIR / "ddi.csv", encoding="utf-8", newline="") as fh:
        ddi_rows = list(csv.DictReader(fh))
    matched_mech = 0
    for i, r in enumerate(ddi_rows, start=1):
        a, b = r["ddinter_id_a"], r["ddinter_id_b"]
        mid = mech_index.get((a, b))
        if mid:
            matched_mech += 1
        conn.execute(
            "INSERT INTO ddi (id, ddinter_id_a, ddinter_id_b, level, mechanism_id, source_id) VALUES (?,?,?,?,?,?)",
            (i, a, b, r["level"], mid, f"DDInter2.0:{a}/{b}"),
        )

    # ---- 别名表 ----
    with open(PROC_DIR / "alias.csv", encoding="utf-8", newline="") as fh:
        conn.executemany(
            "INSERT INTO alias (alias, kind, ddinter_id) VALUES (?,?,?)",
            [(r["alias"], r["kind"], r["ddinter_id"]) for r in csv.DictReader(fh)],
        )

    # ---- 模板表 ----
    for t in tpl_curated:
        ids = [name2id[n] for n in t["drugs"] if n in name2id]
        missing = [n for n in t["drugs"] if n not in name2id]
        if missing:
            print(f"  [warn] 模板 {t['id']} 药名未命中: {missing}")
        conn.execute(
            "INSERT INTO template (id, name, desc_text, expected, drugs_json) VALUES (?,?,?,?,?)",
            (t["id"], t["name"], t["desc"], t["expected"], json.dumps(ids, ensure_ascii=False)),
        )

    # ---- meta ----
    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?,?)",
        [
            ("source", "DDInter 2.0 (https://ddinter2.scbdd.com/, CC BY-NC-SA 4.0)"),
            ("built_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            ("drugs", str(len(drugs))),
            ("ddi_pairs", str(len(ddi_rows))),
            ("mechanisms", str(len(mech_curated))),
            ("aliases", str(conn.execute("SELECT COUNT(*) FROM alias").fetchone()[0])),
        ],
    )
    conn.commit()

    # ---- 统计输出 ----
    from collections import Counter
    level_dist = dict(Counter(r["level"] for r in ddi_rows))
    print(f"数据库          : {DB_PATH} ({DB_PATH.stat().st_size // 1024 // 1024} MB)")
    print(f"drug 表         : {len(drugs)} 行")
    print(f"ddi 表          : {len(ddi_rows)} 行（分级分布 {level_dist}）")
    print(f"mechanism 表    : {len(mech_curated)} 条人工审编（成功挂接 {matched_mech} 条 DDI）")
    print(f"alias 表        : {conn.execute('SELECT COUNT(*) FROM alias').fetchone()[0]} 行")
    print(f"template 表     : {len(tpl_curated)} 个模板")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

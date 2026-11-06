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
DROP TABLE IF EXISTS dupli;
DROP TABLE IF EXISTS dfi;
DROP TABLE IF EXISTS ddsi;
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

-- ============ 其他相互作用（DDInter 网页接口，官方无 CSV） ============

-- 药物-疾病禁忌（DDSI）
CREATE TABLE ddsi (
  id             INTEGER PRIMARY KEY,
  ddinter_id     TEXT NOT NULL REFERENCES drug(ddinter_id),
  disease_en     TEXT NOT NULL,
  disease_cn     TEXT,
  level          TEXT NOT NULL CHECK (level IN ('Major','Moderate','Minor')),
  description_en TEXT,
  reference_text TEXT
);
-- 检查时按「药 × 病」双条件查。复合索引让点查落在 0.1ms 量级；
-- 单列 disease_en 索引反而害事：SQLite 在 IN 列表变长时会切去「疾病优先」计划，
-- 扫到 600+ 条带长文本的行，10 药场景从 0.09ms 劣化到 6.7ms。故不建。
CREATE INDEX idx_ddsi_drug_disease ON ddsi(ddinter_id, disease_en);
-- 疾病选择器要按疾病聚合计数，覆盖索引避免回表读大文本（17.4ms → 1.3ms）
CREATE INDEX idx_ddsi_cover ON ddsi(disease_en, disease_cn, level);

-- 药物-食物相互作用（DFI）。源接口把 mechanism 字段误命名为 magnesium，清洗时已按语义归位
CREATE TABLE dfi (
  id             INTEGER PRIMARY KEY,
  ddinter_id     TEXT NOT NULL REFERENCES drug(ddinter_id),
  food_en        TEXT NOT NULL,
  food_cn        TEXT,
  level          TEXT NOT NULL CHECK (level IN ('Major','Moderate','Minor')),
  interaction_en TEXT,
  management_en  TEXT,
  mechanism_en   TEXT,
  mechanism_cn   TEXT,
  reference_text TEXT
);
CREATE INDEX idx_dfi_drug ON dfi(ddinter_id);
CREATE INDEX idx_dfi_food ON dfi(food_en);

-- 重复用药（治疗重复警告）：同类别 ≥2 种即触发
CREATE TABLE dupli (
  id                INTEGER PRIMARY KEY,
  category_en       TEXT NOT NULL,
  category_cn       TEXT,
  ddinter_id        TEXT NOT NULL REFERENCES drug(ddinter_id),
  combo_trade_name  TEXT,
  combo_ingredients TEXT,
  warning_en        TEXT,
  note_en           TEXT
);
CREATE INDEX idx_dupli_drug ON dupli(ddinter_id);
CREATE INDEX idx_dupli_cat ON dupli(category_en);
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
    drug_ids = {d["ddinter_id"] for d in drugs}

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

    # ---- 其他相互作用（DDSI / DFI / 重复用药）----
    other_counts = {}
    other_files = {
        "ddsi": ("ddsi.csv", ["ddinter_id", "disease_en", "disease_cn", "level", "description_en", "reference_text"]),
        "dfi": ("dfi.csv", ["ddinter_id", "food_en", "food_cn", "level", "interaction_en", "management_en",
                            "mechanism_en", "mechanism_cn", "reference_text"]),
        "dupli": ("dupli.csv", ["category_en", "category_cn", "ddinter_id", "combo_trade_name",
                                "combo_ingredients", "warning_en", "note_en"]),
    }
    for table, (fname, cols) in other_files.items():
        path = PROC_DIR / fname
        if not path.exists():
            print(f"  [warn] 缺少 {fname}，{table} 表留空（运行 clean_other_interactions.py 生成）")
            other_counts[table] = 0
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        rows = [r for r in rows if r["ddinter_id"] in drug_ids]
        conn.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        other_counts[table] = len(rows)

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
            ("ddsi_rows", str(other_counts.get("ddsi", 0))),
            ("dfi_rows", str(other_counts.get("dfi", 0))),
            ("dupli_rows", str(other_counts.get("dupli", 0))),
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
    print(f"ddsi 表         : {other_counts.get('ddsi', 0)} 行（药物-疾病禁忌）")
    print(f"dfi 表          : {other_counts.get('dfi', 0)} 行（药物-食物）")
    print(f"dupli 表        : {other_counts.get('dupli', 0)} 行（重复用药）")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

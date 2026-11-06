"""
其他相互作用检查（DDInter 三类数据，官方仅提供网页接口）：
  - DDSI 药物-疾病禁忌：需要患者基础疾病上下文，未提供则跳过
  - DFI  药物-食物相互作用：无需上下文，按药单直接命中
  - 重复用药：同一治疗类别出现 ≥2 种药即告警

设计原则：
  * 只做查询与聚合，不臆造中文医学结论——原文为英文，中文只给「风险等级 + 类别 + 机制标签」，
    具体描述与参考文献保留英文原文供核对。
  * 返回结构与 DDI 检查保持同样的「诚实边界」：未命中不等于安全。
"""
from __future__ import annotations

import sqlite3

LEVEL_CN = {"Major": "严重", "Moderate": "中度", "Minor": "轻微"}
LEVEL_ORDER = {"Major": 0, "Moderate": 1, "Minor": 2}


def _brief(row) -> dict:
    return {
        "ddinter_id": row["ddinter_id"],
        "name_cn": row["name_cn"] or row["name_en"],
        "name_en": row["name_en"],
        "category": row["category"],
    }


def list_diseases(conn, limit: int = 80) -> list[dict]:
    """供前端疾病选择器：按收录条目数排序的常见基础疾病。"""
    rows = conn.execute(
        """
        SELECT disease_en,
               MAX(disease_cn) AS disease_cn,
               COUNT(*) AS n,
               SUM(CASE WHEN level = 'Major' THEN 1 ELSE 0 END) AS major
        FROM ddsi
        GROUP BY disease_en
        ORDER BY n DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "name_en": r["disease_en"],
            "name_cn": r["disease_cn"] or r["disease_en"],
            "count": r["n"],
            "major": r["major"] or 0,
        }
        for r in rows
    ]


def _ddsi_rows(conn, ids: list[str], diseases: list[str]):
    """药物 × 疾病点查。

    显式 `INDEXED BY` 固定走复合索引：不加提示时 SQLite 在 `IN` 列表变长后会切到
    「疾病优先」计划（先按 disease_en 取 600+ 条带长描述的行再过滤药），10 药场景
    实测 0.09ms → 6.7ms。索引在 init_db 中固定创建；旧库缺索引时退回默认计划。
    """
    ph_ids = ",".join("?" * len(ids))
    ph_dis = ",".join("?" * len(diseases))
    sql = (
        "SELECT ddinter_id, disease_en, disease_cn, level, description_en, reference_text "
        "FROM ddsi {hint} WHERE ddinter_id IN ({ids}) AND disease_en IN ({dis})"
    )
    args = (*ids, *diseases)
    try:
        return conn.execute(
            sql.format(hint="INDEXED BY idx_ddsi_drug_disease", ids=ph_ids, dis=ph_dis), args
        ).fetchall()
    except sqlite3.OperationalError:  # 索引缺失（旧版数据库）
        return conn.execute(sql.format(hint="", ids=ph_ids, dis=ph_dis), args).fetchall()


def check_disease(conn, drugs: list, diseases: list[str]) -> list[dict]:
    """药物 × 疾病 禁忌。diseases 用英文规范名（与 ddsi.disease_en 一致）。"""
    if not drugs or not diseases:
        return []
    ids = [d["ddinter_id"] for d in drugs]
    rows = _ddsi_rows(conn, ids, diseases)

    by_id = {d["ddinter_id"]: d for d in drugs}
    out = []
    for r in rows:
        drug = by_id.get(r["ddinter_id"])
        if drug is None:
            continue
        dis_cn = r["disease_cn"] or r["disease_en"]
        out.append(
            {
                "drug": _brief(drug),
                "disease_en": r["disease_en"],
                "disease_cn": dis_cn,
                "level": r["level"],
                "level_cn": LEVEL_CN[r["level"]],
                "summary_cn": f"患有「{dis_cn}」时使用 {_brief(drug)['name_cn']} 属{LEVEL_CN[r['level']]}风险，需由医师评估后决定是否使用。",
                "description_en": r["description_en"],
                "reference_text": r["reference_text"],
            }
        )
    out.sort(key=lambda x: (LEVEL_ORDER[x["level"]], x["disease_en"], x["drug"]["name_en"]))
    return out


def check_food(conn, drugs: list) -> list[dict]:
    """药物 × 食物（含烟酒）。无需上下文。"""
    if not drugs:
        return []
    ids = [d["ddinter_id"] for d in drugs]
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT ddinter_id, food_en, food_cn, level, interaction_en, management_en,
               mechanism_en, mechanism_cn, reference_text
        FROM dfi
        WHERE ddinter_id IN ({ph})
        """,
        tuple(ids),
    ).fetchall()

    by_id = {d["ddinter_id"]: d for d in drugs}
    out = []
    for r in rows:
        drug = by_id.get(r["ddinter_id"])
        if drug is None:
            continue
        food_cn = r["food_cn"] or r["food_en"]
        mech = r["mechanism_cn"] or r["mechanism_en"] or "未标注"
        out.append(
            {
                "drug": _brief(drug),
                "food_en": r["food_en"],
                "food_cn": food_cn,
                "level": r["level"],
                "level_cn": LEVEL_CN[r["level"]],
                "mechanism_cn": mech,
                "summary_cn": f"与「{food_cn}」同服可能产生{LEVEL_CN[r['level']]}风险（机制：{mech}）。",
                "interaction_en": r["interaction_en"],
                "management_en": r["management_en"],
                "reference_text": r["reference_text"],
            }
        )
    out.sort(key=lambda x: (LEVEL_ORDER[x["level"]], x["food_en"], x["drug"]["name_en"]))
    return out


def check_duplication(conn, drugs: list) -> list[dict]:
    """治疗重复：同一类别下出现 ≥2 种药。返回按类别聚合的告警组。"""
    if len(drugs) < 2:
        return []
    ids = [d["ddinter_id"] for d in drugs]
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT category_en, category_cn, ddinter_id, combo_trade_name, warning_en, note_en
        FROM dupli
        WHERE ddinter_id IN ({ph})
        """,
        tuple(ids),
    ).fetchall()

    by_id = {d["ddinter_id"]: d for d in drugs}
    groups: dict[str, dict] = {}
    for r in rows:
        drug = by_id.get(r["ddinter_id"])
        if drug is None:
            continue
        g = groups.setdefault(
            r["category_en"],
            {
                "category_en": r["category_en"],
                "category_cn": r["category_cn"] or r["category_en"],
                "drugs": {},
                "warning_en": r["warning_en"],
                "note_en": r["note_en"],
            },
        )
        g["drugs"][r["ddinter_id"]] = _brief(drug)

    out = []
    for g in groups.values():
        if len(g["drugs"]) < 2:
            continue
        drugs_in = sorted(g["drugs"].values(), key=lambda d: d["name_en"])
        names = "、".join(d["name_cn"] for d in drugs_in)
        out.append(
            {
                "category_en": g["category_en"],
                "category_cn": g["category_cn"],
                "drugs": drugs_in,
                "summary_cn": f"药单中有 {len(drugs_in)} 种药物同属「{g['category_cn']}」类别（{names}），构成治疗重复，建议核对是否为重复用药。",
                "warning_en": g["warning_en"],
                "note_en": g["note_en"],
            }
        )
    out.sort(key=lambda x: (-len(x["drugs"]), x["category_en"]))
    return out


def check_other(conn, drugs: list, diseases: list[str] | None = None) -> dict:
    """汇总三类检查，附带各自的计数与整体等级。"""
    diseases = diseases or []
    disease_risks = check_disease(conn, drugs, diseases)
    food_risks = check_food(conn, drugs)
    duplications = check_duplication(conn, drugs)

    def tally(items):
        return {
            level: sum(1 for i in items if i["level"] == level)
            for level in ("Major", "Moderate", "Minor")
        }

    d_tally, f_tally = tally(disease_risks), tally(food_risks)
    overall = "gray"
    if d_tally["Major"] or f_tally["Major"]:
        overall = "red"
    elif d_tally["Moderate"] or f_tally["Moderate"] or duplications:
        overall = "orange"
    elif d_tally["Minor"] or f_tally["Minor"]:
        overall = "green"

    note = ""
    if not diseases:
        note = "未提供基础疾病信息，已跳过药物-疾病禁忌检查。"
    elif not disease_risks:
        note = "所选基础疾病与药单中的药物无收录禁忌记录——未收录不代表安全。"

    return {
        "diseases_checked": diseases,
        "disease_risks": disease_risks,
        "food_risks": food_risks,
        "duplications": duplications,
        "other_summary": {
            "disease": d_tally,
            "food": f_tally,
            "duplication_groups": len(duplications),
            "overall": overall,
        },
        "other_note": note,
    }

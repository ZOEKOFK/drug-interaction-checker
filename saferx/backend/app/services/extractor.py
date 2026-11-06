"""
NLP 关系抽取演示（离线规则基线）。

正式版将加载 ml/artifacts 中的 UIE / BioBERT 导出模型；
本模块保证「AI 实验室」页面在后端就绪、模型未训练时即可演示完整闭环：
文本 -> 实体识别 -> 三元组抽取 -> 与主库比对（已收录 / 新增候选）。
"""
from .alias import drug_brief

LEVEL_CN = {"Major": "严重", "Moderate": "中度", "Minor": "轻微", "Unknown": "分级未知"}


def extract(conn, text: str) -> dict:
    # 1) 实体识别：词典匹配（中文注释名 + 英文名，取最长命中去重叠）
    entities = []
    for row in conn.execute("SELECT * FROM drug").fetchall():
        for name in filter(None, (row["name_cn"], row["name_en"])):
            start = 0
            while True:
                idx = text.find(name, start)
                if idx == -1:
                    break
                entities.append(
                    {"start": idx, "end": idx + len(name), "text": name, "drug": row}
                )
                start = idx + len(name)

    entities.sort(key=lambda e: (e["start"], -(e["end"] - e["start"])))
    merged = []
    for e in entities:
        if merged and e["start"] < merged[-1]["end"]:
            continue
        merged.append(e)

    # 2) 三元组抽取：文中共现的两两药物对 -> 查主库
    triples = []
    seen = set()
    for i in range(len(merged)):
        for j in range(i + 1, len(merged)):
            a, b = merged[i]["drug"], merged[j]["drug"]
            if a["ddinter_id"] == b["ddinter_id"]:
                continue
            key = tuple(sorted((a["ddinter_id"], b["ddinter_id"])))
            if key in seen:
                continue
            seen.add(key)
            rec = conn.execute(
                """
                SELECT d.level, m.text_cn AS mech_cn
                FROM ddi d LEFT JOIN mechanism m ON m.id = d.mechanism_id
                WHERE d.ddinter_id_a = ? AND d.ddinter_id_b = ?
                """,
                key,
            ).fetchone()
            if rec:
                triples.append(
                    {
                        "drug_a": drug_brief(a),
                        "drug_b": drug_brief(b),
                        "status": "known",
                        "level": rec["level"],
                        "level_cn": LEVEL_CN[rec["level"]],
                        "mechanism_cn": rec["mech_cn"]
                        or "主库已收录该药对（官方暂无机制描述），可在 DDInter 官网查看详情。",
                        "confidence": 0.92,
                    }
                )
            else:
                triples.append(
                    {
                        "drug_a": drug_brief(a),
                        "drug_b": drug_brief(b),
                        "status": "new",
                        "level": None,
                        "level_cn": None,
                        "mechanism_cn": "主库未收录该药物对，建议人工核实原文后评审入库（AI 提议 + 人工把关）。",
                        "confidence": 0.78,
                    }
                )

    return {
        "entities": [
            {
                "start": e["start"],
                "end": e["end"],
                "text": e["text"],
                "drug": drug_brief(e["drug"]),
            }
            for e in merged
        ],
        "triples": triples,
    }

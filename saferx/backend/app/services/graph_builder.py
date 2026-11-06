"""药单关系子图构建（节点/边/风险着色，ECharts 直接可用）。"""
from .alias import drug_brief

LEVEL_COLOR = {
    "Major": "#A32D2D",
    "Moderate": "#854F0B",
    "Minor": "#3B6D11",
    "Unknown": "#8CA096",
}
LEVEL_BORDER = {  # 节点描边 = 该药涉及的最高已知分级
    3: "#A32D2D",
    2: "#854F0B",
    1: "#3B6D11",
    0: "#DCE9E4",
}
_RANK = {"Major": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}


def build_graph(conn, med_ids: list[str]) -> dict:
    """med_ids: 已归一化的 DDInter ID 列表 -> {nodes, links}"""
    node_rows: dict[str, object] = {}
    for mid in med_ids:
        row = conn.execute("SELECT * FROM drug WHERE ddinter_id = ?", (mid,)).fetchone()
        if row:
            node_rows[mid] = row

    nodes = []
    links = []
    degree = {mid: 0 for mid in node_rows}
    max_rank = {mid: 0 for mid in node_rows}

    ids = sorted(node_rows)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            rec = conn.execute(
                "SELECT level FROM ddi WHERE ddinter_id_a = ? AND ddinter_id_b = ?",
                (a, b),
            ).fetchone()
            if rec is None:
                continue
            level = rec["level"]
            degree[a] += 1
            degree[b] += 1
            max_rank[a] = max(max_rank[a], _RANK[level])
            max_rank[b] = max(max_rank[b], _RANK[level])
            links.append(
                {
                    "source": a,
                    "target": b,
                    "value": level,
                    "lineStyle": {
                        "color": LEVEL_COLOR[level],
                        "width": 4 if level == "Major" else 2.5,
                    },
                    "label": {"show": False},
                }
            )

    for mid, row in node_rows.items():
        brief = drug_brief(row)
        nodes.append(
            {
                "id": mid,
                "name": brief["name_cn"],
                "name_en": brief["name_en"],
                "category": brief["category"],
                "degree": degree[mid],
                "symbolSize": 16 + min(degree[mid], 6) * 5,
                "borderColor": LEVEL_BORDER[max_rank[mid]],
                "borderWidth": 4 if max_rank[mid] > 0 else 2,
            }
        )
    return {"nodes": nodes, "links": links}

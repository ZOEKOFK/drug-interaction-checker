"""关系子图接口。GET /api/graph"""
from fastapi import APIRouter, Depends

from ...core.db import get_conn
from ...services.alias import resolve_one
from ...services.graph_builder import build_graph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
def graph(ids: str, conn=Depends(get_conn)):
    """当前药单的关系子图 -> {nodes, links}（ECharts 直接可用）。

    ids: 逗号分隔的 DDInter ID 或药名。
    """
    med_ids = []
    seen = set()
    for item in ids.split(","):
        row, _ = resolve_one(conn, item.strip())
        if row and row["ddinter_id"] not in seen:
            seen.add(row["ddinter_id"])
            med_ids.append(row["ddinter_id"])
    return build_graph(conn, med_ids)

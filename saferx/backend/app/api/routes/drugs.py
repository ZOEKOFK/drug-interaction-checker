"""药物搜索与模板接口。GET /api/drugs/search, /api/templates"""
import json

from fastapi import APIRouter, Depends, Query

from ...core.db import get_conn
from ...services.alias import drug_brief, search_drugs

router = APIRouter(prefix="/api/drugs", tags=["drugs"])


@router.get("/search")
def search(q: str = "", limit: int = Query(10, ge=1, le=50), conn=Depends(get_conn)):
    """药名模糊搜索（中文通用名 / 英文 / 拼音首字母）。空 q 返回常用慢病药物。"""
    rows = search_drugs(conn, q, limit)
    return [drug_brief(r) for r in rows]


@router.get("/templates")
def list_templates(conn=Depends(get_conn)):
    """慢病示例模板药单（演示与测试共用）。"""
    out = []
    for t in conn.execute("SELECT * FROM template ORDER BY id").fetchall():
        ids = json.loads(t["drugs_json"])
        drugs = []
        for did in ids:
            row = conn.execute("SELECT * FROM drug WHERE ddinter_id = ?", (did,)).fetchone()
            if row:
                drugs.append(drug_brief(row))
        out.append(
            {
                "id": t["id"],
                "name": t["name"],
                "desc": t["desc_text"],
                "expected": t["expected"],
                "drugs": drugs,
            }
        )
    return out

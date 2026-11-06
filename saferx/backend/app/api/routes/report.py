"""汇总报告接口。GET /api/report —— 聚合数据（导出报告用）。"""
from fastapi import APIRouter, Depends

from ...core.db import get_conn
from ...schemas.check import CheckRequest
from ...services.checker import check_meds

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report")
def report(ids: str, conn=Depends(get_conn)):
    """按药物 ID/药名列表返回汇总报告数据（结构同 /api/check）。"""
    return check_meds(conn, [x.strip() for x in ids.split(",") if x.strip()])


@router.post("/report")
def report_post(req: CheckRequest, conn=Depends(get_conn)):
    return check_meds(conn, req.medications)

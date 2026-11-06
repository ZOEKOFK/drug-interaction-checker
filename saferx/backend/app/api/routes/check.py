"""核心接口。POST /api/check —— 药单两两 DDI 检查。"""
from fastapi import APIRouter, Depends

from ...core.db import get_conn
from ...schemas.check import CheckRequest
from ...services.checker import check_meds

router = APIRouter(prefix="/api", tags=["check"])


@router.post("/check")
def check(req: CheckRequest, conn=Depends(get_conn)):
    """对药单内 C(n,2) 个组合逐一查询，按 DDInter 分级输出风险与处置建议。

    - medications: 药名（中文/英文/拼音）或 DDInter ID，最多 20 项
    - diseases: 可选的基础疾病英文规范名（DDSI 检查需要），见 /api/drugs/diseases
    - 保守策略：同一组合取最高风险等级（存储侧已按唯一索引聚合）
    - 诚实边界：unrecorded_pairs 为库内无记录组合，不代表无相互作用
    - 另返回三类「其他相互作用」：药物-疾病禁忌、药物-食物、治疗重复
    """
    return check_meds(conn, req.medications, req.diseases)

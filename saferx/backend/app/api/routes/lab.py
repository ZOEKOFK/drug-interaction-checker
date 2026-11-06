"""AI 实验室接口。POST /api/lab/extract —— 文献 DDI 关系抽取演示。"""
from fastapi import APIRouter, Depends

from ...core.db import get_conn
from ...schemas.check import ExtractRequest
from ...services.extractor import extract

router = APIRouter(prefix="/api/lab", tags=["lab"])


@router.post("/extract")
def lab_extract(req: ExtractRequest, conn=Depends(get_conn)):
    """输入一段药品说明书/文献文本，抽取 (药物A, 药物B, 相互作用) 三元组并与主库比对。

    当前为规则基线（词典共现）；正式版将加载 ml/artifacts 的 UIE/BioBERT 导出模型。
    """
    return extract(conn, req.text)

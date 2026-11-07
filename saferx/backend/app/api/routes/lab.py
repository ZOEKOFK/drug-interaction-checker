"""AI 实验室接口。POST /api/lab/extract —— 文献 DDI 关系抽取演示。"""
from fastapi import APIRouter, Depends

from ...core.db import get_conn
from ...schemas.check import ExtractRequest
from ...services.extractor import extract

router = APIRouter(prefix="/api/lab", tags=["lab"])


@router.post("/extract")
def lab_extract(req: ExtractRequest, conn=Depends(get_conn)):
    """输入一段药品说明书/文献文本，抽取 (药物A, 药物B, 相互作用) 三元组并与主库比对。

    默认走词典基线（零依赖）；设置 `SAFERX_ML=1` 且 `ml/artifacts/biobert-ner` 存在时，
    自动切换到 BioBERT 序列标注（DDIExtraction 2013 实体 F1 0.877），响应里 `engine` 会标明。
    """
    return extract(conn, req.text, req.use_model)

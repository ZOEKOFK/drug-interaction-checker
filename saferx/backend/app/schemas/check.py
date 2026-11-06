"""Pydantic 请求/响应模型。"""
from typing import Optional

from pydantic import BaseModel, Field


# ---------- 药物 ----------

class DrugBrief(BaseModel):
    ddinter_id: str
    name_cn: str
    name_en: str
    atc: Optional[str] = None
    category: Optional[str] = None


# ---------- 检查 ----------

class CheckRequest(BaseModel):
    """POST /api/check 请求体：药单（药名或 DDInter ID，最多 20 项）。

    diseases 为可选的「患者基础疾病」英文规范名列表（见 GET /api/drugs/diseases），
    提供后才会执行药物-疾病禁忌（DDSI）检查。
    """
    medications: list[str] = Field(default_factory=list, max_length=20)
    diseases: list[str] = Field(default_factory=list, max_length=20)


class CheckPair(BaseModel):
    drug_a: DrugBrief
    drug_b: DrugBrief
    level: str
    level_cn: str
    mechanism_cn: str
    mechanism_en: Optional[str] = None
    management: str
    source_id: str


class UnresolvedItem(BaseModel):
    input: str
    candidates: list[DrugBrief] = Field(default_factory=list)


class CheckSummary(BaseModel):
    Major: int = 0
    Moderate: int = 0
    Minor: int = 0
    Unknown: int = 0
    overall: str = "gray"


class CheckResponse(BaseModel):
    unresolved: list[UnresolvedItem] = Field(default_factory=list)
    pairs: list[CheckPair] = Field(default_factory=list)
    unrecorded_pairs: list[dict] = Field(default_factory=list)
    summary: CheckSummary
    checked_at: str
    data_version: str
    coverage_note: str

    # ---- 其他相互作用（DDInter 网页接口数据）----
    diseases_checked: list[str] = Field(default_factory=list)
    disease_risks: list[dict] = Field(default_factory=list)
    food_risks: list[dict] = Field(default_factory=list)
    duplications: list[dict] = Field(default_factory=list)
    other_summary: dict = Field(default_factory=dict)
    other_note: str = ""
    overall_all: str = "gray"


# ---------- 图谱 ----------

class GraphNode(BaseModel):
    id: str
    name: str
    name_en: str
    category: Optional[str] = None
    degree: int = 0
    symbolSize: float = 16
    borderColor: str = "#DCE9E4"
    borderWidth: int = 2


class GraphLink(BaseModel):
    source: str
    target: str
    value: str
    lineStyle: dict
    label: dict


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


# ---------- 实验室 ----------

class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)

"""NLP 抽取器用例：词典基线的中英文覆盖 + 模型开关 + 归一化边界。

模型层（BioBERT）不在这里测：411MB 权重不该成为 CI 依赖。
模型可用性由 `ml/infer.py --text ...` 手工验证，结果记在 docs/eval_ner_biobert.md。
"""
import pytest


def test_chinese_names_extracted(client):
    """中文整句没有空格，必须逐字滑动才能匹配（曾经的中文召回 bug）。"""
    r = client.post("/api/lab/extract", json={"text": "患者长期口服华法林抗凝，近期加用胺碘酮。"})
    assert r.status_code == 200
    texts = [e["text"] for e in r.json()["entities"]]
    assert "华法林" in texts and "胺碘酮" in texts


def test_english_lowercase_matched(client):
    """英文小写药名要能匹配——词典曾经是大小写敏感的，会漏掉文献里的常规写法。"""
    r = client.post("/api/lab/extract", json={"text": "warfarin combined with amiodarone raises INR."})
    texts = [e["text"] for e in r.json()["entities"]]
    assert "warfarin" in texts and "amiodarone" in texts


def test_alias_synonym_matched(client):
    """Aspirin 的 name_en 是 Acetylsalicylic acid，只能靠别名表命中。"""
    r = client.post("/api/lab/extract", json={"text": "The patient took aspirin 100mg daily."})
    names = [(e["drug"] or {}).get("name_cn") for e in r.json()["entities"]]
    assert "阿司匹林" in names


def test_engine_reported_as_dict_by_default(client):
    """未开 SAFERX_ML 时 engine 必须是 dict，前端据此显示「词典基线」。"""
    r = client.post("/api/lab/extract", json={"text": "华法林与阿司匹林同服"})
    assert r.json()["engine"] == "dict"


def test_force_model_falls_back_when_unavailable(client):
    """显式 use_model=True 但模型/依赖缺失时，必须静默降级而不是 500。"""
    r = client.post("/api/lab/extract", json={"text": "华法林与阿司匹林同服", "use_model": True})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] in ("dict", "biobert")
    assert len(body["triples"]) >= 1


def test_word_boundary_not_broken(client):
    """右边界检查：`aspirin` 不应在 `aspirinase` 这类更长单词里被误切出来。"""
    r = client.post("/api/lab/extract", json={"text": "aspirinase is not a drug name."})
    texts = [e["text"] for e in r.json()["entities"]]
    assert "aspirin" not in texts


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_text_rejected(client, text):
    assert client.post("/api/lab/extract", json={"text": text}).status_code == 422

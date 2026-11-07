"""
NLP 关系抽取（词典基线 + 可选 BioBERT）。

两档实现：
  1. **词典基线**（默认）：名字串匹配，召回受限于药名词表，但零依赖、零延迟。
     在 DDIExtraction 2013 上实体 F1 0.656。
  2. **BioBERT 序列标注**（`SAFERX_ML=1` 且 `ml/artifacts/biobert-ner` 存在时启用）：
     F1 0.877，能识别词表外的商品名与实验化合物。模型 411MB、首次加载约 15s，
     所以默认关闭，避免线上为演示功能付出启动代价。

两档产物结构完全一致，上层路由无需改动。
"""
import os

from .alias import drug_brief

LEVEL_CN = {"Major": "严重", "Moderate": "中度", "Minor": "轻微", "Unknown": "分级未知"}


def _ml_enabled() -> bool:
    return os.getenv("SAFERX_ML", "0") in ("1", "true", "yes")


def _load_infer():
    """把 ml/infer.py 当作可选模块导入；缺失时返回 None（不抛异常）。"""
    try:
        import importlib.util
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        path = root / "ml" / "infer.py"
        if not path.exists():
            return None
        spec = importlib.util.spec_from_file_location("saferx_ml_infer", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001 - 模型层是可选组件，任何异常都降级
        return None


def _exact_drug(conn, name: str):
    """实体名 -> 库内药物，只做精确匹配（模糊匹配在抽取场景会引入误配）。"""
    n = (name or "").strip()
    if not n:
        return None
    for key in {n, n.lower()}:
        row = conn.execute(
            "SELECT d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id WHERE a.alias = ?",
            (key,),
        ).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT * FROM drug WHERE name_en = ? OR name_cn = ? LIMIT 1", (n, n)
    ).fetchone()


def _dict_spans(conn, text: str) -> list[dict]:
    """词典最长匹配，返回 [{start, end, text, drug, source}]。

    大小写不敏感 + 右词边界（与 `pipelines/eval_nlp.py::dict_entities` 同源），
    否则英文文献里小写的 `amiodarone` 会被漏掉——这是词典法最冤的一类错误。
    """
    rows = conn.execute("SELECT * FROM drug").fetchall()
    # 词表 = 药名（中/英）+ 别名（cn/en/synonym）。**不含 pinyin**：
    # 拼音首字母（如 klms）在英文文本里会误匹配大量单词片段。
    # 与 pipelines/eval_nlp.py 的词表口径一致，评测数字才对得上实现。
    vocab: list[tuple[str, object]] = []
    for row in rows:
        for name in filter(None, (row["name_cn"], row["name_en"])):
            vocab.append((name, row))
    for alias_row in conn.execute(
        "SELECT a.alias AS name, d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id "
        "WHERE a.kind IN ('cn','en','synonym')"
    ).fetchall():
        vocab.append((alias_row["name"], alias_row))
    vocab = [(n, r) for n, r in vocab if n and len(n) >= 2]
    vocab.sort(key=lambda x: -len(x[0]))

    # 首字符索引：中文没有空格分隔，必须逐字滑动，线性扫全词表会退化成几十万次比较
    by_head: dict[str, list[tuple[str, object]]] = {}
    for name, row in vocab:
        by_head.setdefault(name[0].lower(), []).append((name.lower(), row))

    low = text.lower()
    n = len(low)
    merged: list[dict] = []
    i = 0
    while i < n:
        cands = by_head.get(low[i])
        hit = None
        if cands:
            for t, row in cands:
                if low.startswith(t, i):
                    end = i + len(t)
                    # 右边界只对 ASCII 字母设限：中文药名后面跟汉字是正常的（「华法林与…」）
                    if end >= n or not (low[end].isascii() and low[end].isalpha()):
                        hit = (i, end, t, row)
                        break
        if hit:
            i0, i1, _, row = hit
            merged.append({"start": i0, "end": i1, "text": text[i0:i1], "drug": row, "source": "dict"})
            i = i1
        elif low[i].isascii() and low[i].isalnum():
            # 英文按词跳过，避免在单词中间起匹配
            while i < n and low[i].isascii() and low[i].isalnum():
                i += 1
        else:
            # 中文逐字前进（无空格可依）；ASCII 标点/空白也走这里
            i += 1
    return merged


def _model_spans(conn, text: str, infer) -> list[dict]:
    """模型 span -> 带 drug 的实体。识别到但库内无对应药物的，drug 为 None。"""
    out = []
    for s in infer.predict(text):
        drug = _exact_drug(conn, s["text"])
        out.append(
            {
                "start": s["start"],
                "end": s["end"],
                "text": s["text"],
                "drug": drug,
                "source": "model",
                "entity_type": s["type"],
            }
        )
    return out


def extract(conn, text: str, use_model: bool | None = None) -> dict:
    """文本 -> 实体 + 三元组。

    use_model=None 时读环境变量 SAFERX_ML；模型不可用则静默回落到词典基线。
    """
    if use_model is None:
        use_model = _ml_enabled()

    entities: list[dict] = []
    engine = "dict"
    if use_model:
        infer = _load_infer()
        if infer is not None and infer.available():
            entities = _model_spans(conn, text, infer)
            engine = "biobert"
            # 模型漏掉的部分用词典补齐（例如中文药名模型未见过的写法）
            for e in _dict_spans(conn, text):
                if any(not (e["end"] <= x["start"] or e["start"] >= x["end"]) for x in entities):
                    continue
                entities.append(e)

    if not entities:
        entities = _dict_spans(conn, text)
        engine = "dict"

    entities.sort(key=lambda e: e["start"])

    # 三元组抽取：文中共现的两两药物对 -> 查主库
    # 只用能归一化到库内的实体；模型识别出的陌生药名单独列出，供人工评审
    known = [e for e in entities if e["drug"] is not None]
    unknown = [
        {"start": e["start"], "end": e["end"], "text": e["text"], "type": e.get("entity_type")}
        for e in entities
        if e["drug"] is None
    ]

    triples = []
    seen = set()
    for i in range(len(known)):
        for j in range(i + 1, len(known)):
            a, b = known[i]["drug"], known[j]["drug"]
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
        "engine": engine,
        "entities": [
            {
                "start": e["start"],
                "end": e["end"],
                "text": e["text"],
                "source": e["source"],
                "drug": drug_brief(e["drug"]) if e["drug"] is not None else None,
            }
            for e in entities
        ],
        "unknown_entities": unknown,
        "triples": triples,
    }

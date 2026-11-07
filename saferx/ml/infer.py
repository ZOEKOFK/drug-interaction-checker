#!/usr/bin/env python
"""
BioBERT 实体识别推理（可选组件）。

设计原则：**默认不加载**。模型权重 411MB，线上服务没必要为演示功能付出这个代价。
只有显式设置 `SAFERX_ML=1` 且产物存在时才会加载，其余情况静默降级到词典基线。

依赖：torch + transformers（不在 backend/requirements.txt 里，见 ml/requirements.txt）。
用法：
    python ml/infer.py --text "Warfarin may increase the risk of bleeding with aspirin."
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = Path(os.getenv("SAFERX_ML_ARTIFACT", ROOT / "ml" / "artifacts" / "biobert-ner"))

# 标签映射**必须**从模型 config 读取：训练时 ENTITY_TYPES 是 set，迭代顺序不稳定，
# 硬编码顺序会静默错位（把 DRUG_N 当成 DRUG），这里只保留一个兜底常量。
_FALLBACK_ID2LABEL = {0: "O"}


def _id2label() -> dict:
    m = _state["model"]
    cfg = getattr(m, "config", None)
    raw = getattr(cfg, "id2label", None) if cfg else None
    if raw:
        return {int(k): v for k, v in raw.items()}
    return _FALLBACK_ID2LABEL

_state: dict = {"model": None, "tokenizer": None, "tried": False, "error": None}


def available() -> bool:
    """产物与依赖是否齐备。不做模型加载，成本接近零。"""
    if not (ARTIFACT / "config.json").exists():
        return False
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _load():
    if _state["model"] is not None or _state["tried"]:
        return _state["model"]
    _state["tried"] = True
    if not available():
        _state["error"] = "模型产物或依赖缺失"
        return None
    try:
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        _state["tokenizer"] = AutoTokenizer.from_pretrained(str(ARTIFACT))
        model = AutoModelForTokenClassification.from_pretrained(str(ARTIFACT))
        model.eval()
        torch.set_num_threads(max(1, min(8, (os.cpu_count() or 4))))
        _state["model"] = model
    except Exception as e:  # noqa: BLE001
        _state["error"] = f"{type(e).__name__}: {e}"
        _state["model"] = None
    return _state["model"]


def _split_long(text: str, max_len: int = 400):
    """超长文本按句末/空白切块，避免 512 截断丢掉后半段实体。"""
    if len(text) <= max_len:
        return [(0, text)]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_len, len(text))
        if end < len(text):
            for sep in ("。", ". ", "\n", "；", ";", " "):
                cut = text.rfind(sep, start + max_len // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        chunks.append((start, text[start:end]))
        start = end
    return chunks


def predict(text: str) -> list[dict]:
    """返回实体 span 列表：{start, end, text, type}。偏移相对原始 text。"""
    model = _load()
    if model is None or not text.strip():
        return []
    import torch

    tok = _state["tokenizer"]
    id2label = _id2label()
    out: list[dict] = []
    for base, chunk in _split_long(text):
        enc = tok(chunk, return_offsets_mapping=True, return_tensors="pt", truncation=True, max_length=512)
        offsets = enc.pop("offset_mapping")[0].tolist()
        with torch.no_grad():
            logits = model(**enc).logits[0]
        preds = logits.argmax(-1).tolist()

        cur = None
        spans = []
        for p, (ts, te) in zip(preds, offsets):
            if te == ts:
                continue
            lab = id2label.get(p, "O")
            if lab.startswith("B-"):
                if cur:
                    spans.append(cur)
                cur = [ts, te, lab[2:]]
            elif lab.startswith("I-") and cur and lab[2:] == cur[2]:
                cur[1] = te
            else:
                if cur:
                    spans.append(cur)
                    cur = None
        if cur:
            spans.append(cur)

        for a, b, t in spans:
            piece = chunk[a:b].strip()
            if piece:
                out.append({"start": base + a, "end": base + b, "text": piece, "type": t})
    return out


def info() -> dict:
    """给 /api/health 或诊断脚本用的状态摘要。"""
    m = _load()
    return {
        "artifact": str(ARTIFACT),
        "available": available(),
        "loaded": m is not None,
        "error": _state["error"],
        "size_mb": round(sum(f.stat().st_size for f in ARTIFACT.glob("*") if f.is_file()) / 1024 / 1024, 1)
        if ARTIFACT.exists()
        else 0,
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    spans = predict(a.text)
    if a.json:
        print(json.dumps({"spans": spans, "info": info()}, ensure_ascii=False, indent=2))
    else:
        print(f"模型状态：{info()}")
        for s in spans:
            print(f"  [{s['type']:6s}] {s['start']}..{s['end']}  {s['text']}")

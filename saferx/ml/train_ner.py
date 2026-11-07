#!/usr/bin/env python
"""
BioBERT 实体识别微调（报告 §8-3 的第三档，长期缺失的那一行）。

背景：`pipelines/eval_nlp.py` 给出了两档结果——词典最长匹配（实体 F1 0.656）与
TF-IDF+LR（关系 micro-F1 0.862），第三行 BioBERT 一直标注「未执行：本机无 GPU」。
本脚本用 CPU 把这一行补上：在 DDIExtraction 2013 上微调 BioBERT 做**序列标注**
（BIO 标记，四类实体），补的正是瓶颈所在——实体识别（词典法 recall 仅 0.506）。

为什么是实体识别而不是关系分类：评测显示关系四分类的 TF-IDF+LR 已达 0.862，
接近该语料的上限；而端到端 F1 被实体召回拖住。所以算力应该花在序列标注上。

口径：token 级 BIO 精确匹配（seqeval entity-level），与文献报告的 NER F1 可比；
与 `eval_nlp.py` 的 char-span 精确匹配口径接近但不完全相同，报告中已注明。

用法：
    python ml/train_ner.py --epochs 3                 # 全量训练（CPU 约 40~60 分钟）
    python ml/train_ner.py --limit 40 --epochs 1      # 快速冒烟
    python ml/train_ner.py --model bert-base-cased    # 换骨干
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.eval_nlp import ENTITY_TYPES, load_split, sentences  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
OUT_MD = ROOT / "docs" / "eval_ner_biobert.md"


def build_dataset(docs, tokenizer, max_len=128, limit=None):
    """把 BRAT 文档切成句、转成 BIO 标签的 token 序列。

    标签体系：O / B-DRUG / I-DRUG / B-GROUP ...（四类实体统一处理，
    因为下游只需要「是不是药、边界在哪」，不区分类别）。

    注意：这里**不做 padding**，交给 collate 按 batch 内最长动态补齐。
    DDI 句子长度差异很大（20~200 token），统一补到 max_len 会让 CPU 训练慢一倍以上。
    """
    label2id = {"O": 0}
    for t in ENTITY_TYPES:
        label2id[f"B-{t}"] = len(label2id)
        label2id[f"I-{t}"] = len(label2id)
    id2label = {v: k for k, v in label2id.items()}

    feats = []
    for doc in docs[:limit] if limit else docs:
        text = doc["text"]
        ents = [(e["start"], e["end"], e["type"]) for e in doc["ents"].values()]
        for s0, s1 in sentences(text):
            sent = text[s0:s1]
            if not sent.strip():
                continue
            # 句子内实体（要求完全落在句内）
            local = [(a - s0, b - s0, t) for a, b, t in ents if a >= s0 and b <= s1]
            enc = tokenizer(sent, return_offsets_mapping=True, truncation=True, max_length=max_len)
            labels = []
            for (ts, te) in enc["offset_mapping"]:
                if ts == te:  # [CLS] / [SEP] 等特殊符号，不参与损失
                    labels.append(-100)
                    continue
                hit = None
                for a, b, t in local:
                    if ts >= a and te <= b:
                        hit = (t, ts <= a)
                        break
                if hit is None:
                    labels.append(0)
                else:
                    t, is_begin = hit
                    labels.append(label2id[f"B-{t}" if is_begin else f"I-{t}"])
            if not enc["input_ids"]:
                continue
            feats.append(
                {
                    "input_ids": enc["input_ids"],
                    "attention_mask": enc["attention_mask"],
                    "labels": labels,
                    "gold": [(a + s0, b + s0, t) for a, b, t in local],
                    "offsets": [(ts + s0, te + s0) for ts, te in enc["offset_mapping"]],
                    "doc": doc["name"],
                }
            )
    return feats, label2id, id2label


def decode_spans(feat, preds, id2label):
    """把 token 预测还原成 char span 列表（合并连续的 I-*）。"""
    spans = []
    cur = None
    for p, (ts, te) in zip(preds, feat["offsets"]):
        if te == ts:  # special token
            continue
        lab = id2label[p]
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
    return [(a, b, t) for a, b, t in spans]


def prf(pred, gold):
    pred, gold = set(pred), set(gold)
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f, tp, len(pred), len(gold)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dmis-lab/biobert-base-cased-v1.2")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--max-len", type=int, default=128)
    ap.add_argument("--limit", type=int, default=None, help="只用前 N 篇文档（冒烟用）")
    ap.add_argument("--seed", type=int, default=20261107)
    args = ap.parse_args()

    import numpy as np
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))

    print(f"骨干: {args.model}｜CPU 线程 {torch.get_num_threads()}")
    tok = AutoTokenizer.from_pretrained(args.model)
    t0 = time.time()
    train_docs = load_split("train", args.limit)
    test_docs = load_split("test", args.limit)
    tr, _, id2label = build_dataset(train_docs, tok, args.max_len)
    te, _, _ = build_dataset(test_docs, tok, args.max_len)
    print(f"语料: train {len(train_docs)} 篇 / {len(tr)} 句｜test {len(test_docs)} 篇 / {len(te)} 句｜建集 {time.time() - t0:.1f}s")

    label2id = {v: k for k, v in id2label.items()}
    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(id2label),
        id2label=id2label,
        label2id=label2id,
    )

    class DS(Dataset):
        def __len__(self):
            return len(tr)

        def __getitem__(self, i):
            return tr[i]

    def collate(batch):
        """按 batch 内最长动态补齐，label 用 -100 占位。"""
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.zeros(len(batch), n, dtype=torch.long)
        mask = torch.zeros(len(batch), n, dtype=torch.long)
        lab = torch.full((len(batch), n), -100, dtype=torch.long)
        for i, b in enumerate(batch):
            L = len(b["input_ids"])
            ids[i, :L] = torch.tensor(b["input_ids"])
            mask[i, :L] = torch.tensor(b["attention_mask"])
            lab[i, :L] = torch.tensor(b["labels"])
        return ids, mask, lab

    dl = DataLoader(DS(), batch_size=args.batch, shuffle=True, collate_fn=collate)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total = len(dl) * args.epochs
    sched = torch.optim.lr_scheduler.LinearLR(opt, start_factor=1.0, end_factor=0.1, total_iters=int(total))

    model.train()
    step = 0
    t_start = time.time()
    for ep in range(int(args.epochs)):
        acc_loss = 0.0
        for ids, mask, labels in dl:
            out = model(input_ids=ids, attention_mask=mask, labels=labels)
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            acc_loss += out.loss.item()
            step += 1
            if step % 20 == 0:
                el = time.time() - t_start
                eta = el / step * (total - step)
                print(f"  ep{ep + 1} step {step}/{int(total)} loss {acc_loss / 20:.4f} "
                      f"| {el / 60:.1f} min elapsed, ETA {eta / 60:.1f} min", flush=True)
                acc_loss = 0.0
    train_min = (time.time() - t_start) / 60
    print(f"训练完成，用时 {train_min:.1f} 分钟")

    # ---------------- 评测 ----------------
    model.eval()
    all_pred, all_gold = [], []
    per_type = {t: [[], []] for t in ENTITY_TYPES}  # [pred, gold]
    with torch.no_grad():
        for i in range(0, len(te), args.batch):
            chunk = te[i : i + args.batch]
            n = max(len(c["input_ids"]) for c in chunk)
            ids = torch.zeros(len(chunk), n, dtype=torch.long)
            mask = torch.zeros(len(chunk), n, dtype=torch.long)
            for j, c in enumerate(chunk):
                L = len(c["input_ids"])
                ids[j, :L] = torch.tensor(c["input_ids"])
                mask[j, :L] = torch.tensor(c["attention_mask"])
            preds = model(input_ids=ids, attention_mask=mask).logits.argmax(-1).tolist()
            for c, p in zip(chunk, preds):
                # 只解码真实 token 段（去掉 batch 补齐的部分）
                spans = decode_spans(c, p[: len(c["offsets"])], id2label)
                all_pred += spans
                all_gold += c["gold"]
                for t in ENTITY_TYPES:
                    per_type[t][0] += [s for s in spans if s[2] == t]
                    per_type[t][1] += [s for s in c["gold"] if s[2] == t]

    P, R, F, tp, npred, ngold = prf(all_pred, all_gold)
    print(f"\n实体识别: P {P:.4f} / R {R:.4f} / F1 {F:.4f}  (TP {tp} / pred {npred} / gold {ngold})")

    # ---------------- 产物 ----------------
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(ARTIFACTS / "biobert-ner")
    tok.save_pretrained(ARTIFACTS / "biobert-ner")
    meta = {
        "model": args.model,
        "epochs": args.epochs,
        "batch": args.batch,
        "lr": args.lr,
        "max_len": args.max_len,
        "train_sentences": len(tr),
        "test_sentences": len(te),
        "precision": P,
        "recall": R,
        "f1": F,
        "train_minutes": round(train_min, 1),
        "device": "cpu",
    }
    (ARTIFACTS / "ner_metrics.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(
        f"| {t} | {prf(*per_type[t])[0]:.3f} | {prf(*per_type[t])[1]:.3f} | {prf(*per_type[t])[2]:.3f} |"
        for t in ENTITY_TYPES
    )
    OUT_MD.write_text(
        f"""# BioBERT 实体识别微调（§8-3 第三档）

> 由 `ml/train_ner.py` 自动生成，可复现。
> 骨干：`{args.model}`｜设备：CPU（{torch.get_num_threads()} 线程）｜训练 {train_min:.1f} 分钟

## 设置

| 项 | 值 |
|---|---|
| 语料 | DDIExtraction 2013（BRAT），train {len(train_docs)} 篇 / test {len(test_docs)} 篇 |
| 句子数 | train {len(tr)} / test {len(te)} |
| 任务 | 序列标注，四类实体统一 BIO（DRUG / GROUP / BRAND / DRUG_N） |
| 超参 | epochs {args.epochs} / batch {args.batch} / lr {args.lr} / max_len {args.max_len} |
| 评测 | token 级 BIO 精确匹配（entity-level P/R/F1），span 起止完全一致才算对 |

## 结果

| 指标 | 数值 |
|---|---|
| Precision | **{P:.4f}** |
| Recall | **{R:.4f}** |
| F1 | **{F:.4f}** |
| TP / 预测 / 金标 | {tp} / {npred} / {ngold} |

### 分类型

| 类型 | P | R | F1 |
|---|---|---|---|
{rows}

## 与词典基线的对比

| 方案 | P | R | F1 |
|---|---|---|---|
| 词典最长匹配（`eval_nlp.py`） | 0.934 | 0.506 | 0.656 |
| **BioBERT 微调（本表）** | **{P:.3f}** | **{R:.3f}** | **{F:.3f}** |

## 解读

1. **补上了长期空着的第三行**，而且是在 CPU 上真实跑出来的，不是引用文献数字。
2. 关键看 **Recall**：词典法 0.506 的瓶颈是"词表外的商品名、缩写、实验化合物全靠不上"，
   序列标注能从上下文推断边界，这正是 §8-3 结论里指出的改进方向。
3. 口径差异：本表是 token 级 BIO 匹配，词典法是 char-span 精确匹配。两者接近但不等价，
   后者更严格（一个字符错位就判错）。因此这里的 F1 与 0.656 只能作大致对比，
   不宜当作"提升 X 倍"的结论。
4. 单模型单次运行，未做超参搜索与多 seed 平均；CPU 条件下一轮约 {train_min:.0f} 分钟，
   扫参成本过高。数字应视为该骨干在此语料上的**下界**。

## 复现

```bash
python ml/train_ner.py --epochs 3
```

产物：`ml/artifacts/biobert-ner/`（权重 + 分词器）、`ml/artifacts/ner_metrics.json`
""",
        encoding="utf-8",
    )
    print(f"✓ 权重 -> {ARTIFACTS / 'biobert-ner'}")
    print(f"✓ 报告 -> {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

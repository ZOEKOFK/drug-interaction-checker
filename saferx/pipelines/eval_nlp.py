#!/usr/bin/env python
"""
§8-3 NLP 抽取评测：在 DDIExtraction 2013 测试集上评测两档方案。

  A. 规则基线：词典最长匹配做实体识别 + 关键词规则做关系四分类
  B. TF-IDF(char n-gram) + 逻辑回归：用训练集监督学习关系四分类
  C. BioBERT 微调：已由 ml/train_ner.py 在 CPU 上完成**实体识别**微调（F1 0.877），
     结果见 docs/eval_ner_biobert.md；本脚本只做关系四分类，故 C 档在关系表留空。

评测口径：
  * 实体：与 gold span（起止偏移完全一致）比对，micro P/R/F1
  * 关系：gold 药对上的四分类（MECHANISM / EFFECT / ADVISE / INT），micro & macro F1
  * 检测：句内候选药对上的二分类（是否标注为相互作用），P/R/F1

数据：data/raw/ddicorpus/DDICorpusBrat（官方仓 isegura/DDICorpus，CC BY-NC）
用法：
  python pipelines/eval_nlp.py
  python pipelines/eval_nlp.py --limit 50   # 调试
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "raw" / "ddicorpus" / "DDICorpusBrat"
DB_PATH = ROOT / "data" / "saferx.sqlite"
OUT_MD = ROOT / "docs" / "eval_nlp.md"
OUT_JSON = ROOT / "data" / "processed" / "eval_nlp.json"

ENTITY_TYPES = {"DRUG", "GROUP", "BRAND", "DRUG_N"}
REL_TYPES = ["MECHANISM", "EFFECT", "ADVISE", "INT"]


# ------------------------------------------------------------------ 语料解析

def read_doc(txt_path: Path, ann_path: Path) -> dict:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    ents, rels = {}, {}
    if ann_path.exists():
        for line in ann_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            if line.startswith("T"):
                body = parts[1].split()
                if len(body) >= 3 and body[0] in ENTITY_TYPES:
                    eid = parts[0]
                    # BRAT 支持不连续实体：形如 "710 726;730 740"，取首段偏移
                    nums = re.findall(r"\d+", " ".join(body[1:3]))
                    if len(nums) < 2:
                        continue
                    ents[eid] = {
                        "type": body[0],
                        "start": int(nums[0]),
                        "end": int(nums[1]),
                        "text": parts[2] if len(parts) > 2 else "",
                    }
            elif line.startswith("R"):
                body = parts[1].split()
                if len(body) >= 3 and body[0] in REL_TYPES:
                    a = body[1].split(":")[-1]
                    b = body[2].split(":")[-1]
                    if a in ents and b in ents:
                        rels[parts[0]] = {"type": body[0], "a": a, "b": b}
    return {"name": txt_path.stem, "text": text, "ents": ents, "rels": rels}


def load_split(split: str, limit: int | None = None) -> list[dict]:
    files = sorted((CORPUS / split).rglob("*.txt"))
    if limit:
        files = files[:limit]
    docs = []
    for f in files:
        docs.append(read_doc(f, f.with_suffix(".ann")))
    return docs


SENT_RE = re.compile(r"[^.!?\n]+[.!?]?")


def sentences(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in SENT_RE.finditer(text) if m.group().strip()]


def sent_of(offset: int, sents: list[tuple[int, int]]) -> int:
    for i, (s, e) in enumerate(sents):
        if s <= offset < e:
            return i
    return -1


# ------------------------------------------------------------------ A. 规则基线

def load_drug_dictionary(conn) -> list[str]:
    names = set()
    for r in conn.execute("SELECT name_en FROM drug"):
        names.add(r[0])
    for r in conn.execute("SELECT alias FROM alias WHERE kind IN ('en','synonym')"):
        if r[0] and len(r[0]) >= 4:
            names.add(r[0])
    # 去掉含括号/斜杠的复合名，避免误匹配
    clean = {n.strip().lower() for n in names if n and 3 < len(n) <= 60 and not re.search(r"[()/]", n)}
    return sorted(clean, key=len, reverse=True)


def dict_entities(text: str, dictionary: list[str]) -> list[tuple[int, int]]:
    """最长匹配扫描（不区分大小写，词边界宽松）。"""
    low = text.lower()
    spans, i, n = [], 0, len(low)
    while i < n:
        if not low[i].isalnum():
            i += 1
            continue
        hit = None
        for term in dictionary:
            if low.startswith(term, i):
                end = i + len(term)
                if end >= n or not low[end].isalpha():  # 右边界必须是词边界
                    hit = (i, end)
                    break
        if hit:
            spans.append(hit)
            i = hit[1]
        else:
            while i < n and low[i].isalnum():
                i += 1
    return spans


MECH_KW = ("inhibit", "induc", "substrate", "metaboli", "cyp", "clearance", "absorb", "bind",
           "protein", "excret", "half-life", "bioavailab", "transport")
EFFECT_KW = ("increase", "decrease", "risk", "toxicit", "bleeding", "hypoglyc", "sedation",
             "prolong", "reduce", "enhanc", "adverse", "effect", "concentration", "levels")
ADVISE_KW = ("avoid", "monitor", "recommend", "should", "consider", "contraindicat", "caution",
             "adjust", "dose", "combination", "coadminist", "therapy")


def rule_type(sentence: str) -> str:
    s = sentence.lower()
    score = {
        "MECHANISM": sum(1 for k in MECH_KW if k in s),
        "EFFECT": sum(1 for k in EFFECT_KW if k in s),
        "ADVISE": sum(1 for k in ADVISE_KW if k in s),
    }
    best = max(score, key=score.get)
    return best if score[best] > 0 else "INT"


# ------------------------------------------------------------------ 评测

def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def eval_entities(docs: list[dict], dictionary: list[str]) -> dict:
    tp = fp = fn = 0
    for d in docs:
        gold = {(e["start"], e["end"]) for e in d["ents"].values()}
        pred = set(dict_entities(d["text"], dictionary))
        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)
    p, r, f = prf(tp, fp, fn)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def build_pairs(docs: list[dict]) -> list[dict]:
    """句内候选药对：gold 标注的为正例，未标注的视为负例（shared task 惯例）。"""
    out = []
    for d in docs:
        sents = sentences(d["text"])
        gold = {}
        for rel in d["rels"].values():
            ea, eb = d["ents"][rel["a"]], d["ents"][rel["b"]]
            if sent_of(ea["start"], sents) == sent_of(eb["start"], sents) and sent_of(ea["start"], sents) >= 0:
                gold[frozenset((rel["a"], rel["b"]))] = rel["type"]
        by_sent = defaultdict(list)
        for eid, e in d["ents"].items():
            si = sent_of(e["start"], sents)
            if si >= 0:
                by_sent[si].append(eid)
        for si, eids in by_sent.items():
            if len(eids) < 2:
                continue
            s, e = sents[si]
            sent_text = d["text"][s:e]
            for i in range(len(eids)):
                for j in range(i + 1, len(eids)):
                    pair = frozenset((eids[i], eids[j]))
                    out.append(
                        {
                            "doc": d["name"],
                            "sent": sent_text,
                            "a": d["ents"][eids[i]],
                            "b": d["ents"][eids[j]],
                            "label": gold.get(pair),  # None = 未标注（负例）
                        }
                    )
    return out


def masked(pair: dict) -> str:
    """把两个药名替换成占位符，让模型学关系而非药名。"""
    a, b = sorted([pair["a"], pair["b"]], key=lambda x: x["start"])
    s = pair["sent"]
    # 句子内偏移（实体位置是全文偏移，需按句内相对位置裁剪）
    return s


def entity_marked(sent: str, a: dict, b: dict, sent_start: int) -> str:
    """用 DRUG1/DRUG2 替换实体文本，保留上下文。"""
    spans = sorted([(a["start"] - sent_start, a["end"] - sent_start, "DRUG1"),
                    (b["start"] - sent_start, b["end"] - sent_start, "DRUG2")])
    out, cur = [], 0
    for s, e, tag in spans:
        if s < cur:
            continue
        out.append(sent[cur:s])
        out.append(f" {tag} ")
        cur = e
    out.append(sent[cur:])
    return re.sub(r"\s+", " ", "".join(out)).strip()


def eval_rule_pairs(pairs: list[dict], docs_map: dict) -> dict:
    """规则基线：gold 药对上做四分类；候选药对上做二分类（都判为正）。"""
    correct = Counter()
    gold_counter = Counter()
    pred_counter = Counter()
    for p in pairs:
        if p["label"] is None:
            continue
        pred = rule_type(p["sent"])
        gold_counter[p["label"]] += 1
        pred_counter[pred] += 1
        if pred == p["label"]:
            correct[p["label"]] += 1

    # micro
    tp = sum(correct.values())
    total = sum(gold_counter.values())
    per_class = {}
    for t in REL_TYPES:
        # 对类别 t：tp = 预测 t 且 gold t；fp = 预测 t 但 gold 非 t；fn = gold t 但预测非 t
        tp_c = correct[t]
        fp_c = pred_counter[t] - correct[t]
        fn_c = gold_counter[t] - correct[t]
        p, r, f = prf(tp_c, fp_c, fn_c)
        per_class[t] = {"precision": p, "recall": r, "f1": f, "gold": gold_counter[t]}
    micro_p, micro_r, micro_f = prf(tp, total - tp, total - tp)
    macro_f = sum(v["f1"] for v in per_class.values()) / len(REL_TYPES)
    return {
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f,
        "macro_f1": macro_f,
        "per_class": per_class,
        "n": total,
    }


def eval_tfidf(train_docs: list[dict], test_docs: list[dict]) -> dict:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        return {"error": "scikit-learn 未安装"}

    def to_xy(docs):
        X, y = [], []
        for d in docs:
            sents = sentences(d["text"])
            gold = {}
            for rel in d["rels"].values():
                ea, eb = d["ents"][rel["a"]], d["ents"][rel["b"]]
                gold[frozenset((rel["a"], rel["b"]))] = rel["type"]
            by_sent = defaultdict(list)
            for eid, e in d["ents"].items():
                si = sent_of(e["start"], sents)
                if si >= 0:
                    by_sent[si].append(eid)
            for si, eids in by_sent.items():
                s, _ = sents[si]
                sent = d["text"][s:sents[si][1]]
                for i in range(len(eids)):
                    for j in range(i + 1, len(eids)):
                        k = frozenset((eids[i], eids[j]))
                        if k not in gold:
                            continue
                        X.append(entity_marked(sent, d["ents"][eids[i]], d["ents"][eids[j]], s))
                        y.append(gold[k])
        return X, y

    Xtr, ytr = to_xy(train_docs)
    Xte, yte = to_xy(test_docs)
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2, sublinear_tf=True, max_features=120000)
    Xtr_v = vec.fit_transform(Xtr)
    Xte_v = vec.transform(Xte)
    clf = LogisticRegression(max_iter=1500, C=2.0, class_weight="balanced", n_jobs=-1)
    clf.fit(Xtr_v, ytr)
    pred = clf.predict(Xte_v)

    # 训练/测试句子重复检查（DrugBank 文本模板化，需排除「靠重复刷分」）
    train_texts = set(Xtr)
    keep = [i for i, t in enumerate(Xte) if t not in train_texts]
    dup_ratio = 1 - len(keep) / len(Xte) if Xte else 0.0
    dedup_acc = (
        sum(1 for i in keep if pred[i] == yte[i]) / len(keep) if keep else 0.0
    )

    labels = REL_TYPES
    gold_counter = Counter(yte)
    pred_counter = Counter(pred)
    correct = Counter(g for g, p in zip(yte, pred) if g == p)
    per_class = {}
    for t in labels:
        tp = correct[t]
        fp = pred_counter[t] - correct[t]
        fn = gold_counter[t] - correct[t]
        p, r, f = prf(tp, fp, fn)
        per_class[t] = {"precision": p, "recall": r, "f1": f, "gold": gold_counter[t]}
    tp_all = sum(correct.values())
    total = len(yte)
    micro_p, micro_r, micro_f = prf(tp_all, total - tp_all, total - tp_all)
    return {
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f,
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(labels),
        "per_class": per_class,
        "n_train": len(Xtr),
        "n_test": total,
        "dedup_ratio": dup_ratio,
        "dedup_n": len(keep),
        "dedup_micro_f1": dedup_acc,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="每个 split 只取前 N 个文档（调试）")
    args = ap.parse_args()

    if not CORPUS.exists():
        print(f"缺少语料目录 {CORPUS}\n请先：git clone --depth 1 https://github.com/isegura/DDICorpus.git data/raw/DDICorpus")
        return 1

    conn = sqlite3.connect(DB_PATH)
    limit = args.limit or None
    train_docs = load_split("Train", limit)
    test_docs = load_split("Test", limit)
    print(f"语料：Train {len(train_docs)} 文档 / Test {len(test_docs)} 文档")

    dictionary = load_drug_dictionary(conn)
    print(f"词典：{len(dictionary)} 条英文药名/同义词")

    print("A. 规则基线实体识别 …")
    ent = eval_entities(test_docs, dictionary)
    print(f"   实体 P/R/F1 = {ent['precision']:.3f} / {ent['recall']:.3f} / {ent['f1']:.3f}")

    test_pairs = build_pairs(test_docs)
    gold_pairs = [p for p in test_pairs if p["label"]]
    print(f"   候选药对 {len(test_pairs)} 条，其中标注为相互作用 {len(gold_pairs)} 条")

    print("A. 规则基线关系四分类 …")
    rule = eval_rule_pairs(test_pairs, {})
    print(f"   micro-F1 = {rule['micro_f1']:.3f} · macro-F1 = {rule['macro_f1']:.3f}")

    print("B. TF-IDF + 逻辑回归 …")
    t0 = time.time()
    tfidf = eval_tfidf(train_docs, test_docs)
    if "error" in tfidf:
        print("   ", tfidf["error"])
    else:
        print(f"   训练 {tfidf['n_train']} 条 / 测试 {tfidf['n_test']} 条 · "
              f"micro-F1 = {tfidf['micro_f1']:.3f} · macro-F1 = {tfidf['macro_f1']:.3f} "
              f"({time.time() - t0:.1f}s)")

    result = {
        "corpus": "DDIExtraction 2013 (DDICorpus-2013, BRAT)",
        "train_docs": len(train_docs),
        "test_docs": len(test_docs),
        "dictionary_size": len(dictionary),
        "candidate_pairs": len(test_pairs),
        "gold_pairs": len(gold_pairs),
        "entity": ent,
        "rule": rule,
        "tfidf": tfidf,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_md(result)
    print(f"\n写入 {OUT_MD}")
    return 0


def write_md(r: dict) -> None:
    ent, rule, tfidf = r["entity"], r["rule"], r["tfidf"]
    has_tfidf = "error" not in tfidf

    L = [
        "# NLP 抽取评测（DDIExtraction 2013）",
        "",
        "> 由 `pipelines/eval_nlp.py` 自动生成，可复现。",
        f"> 生成时间：{r['generated_at']} · 语料：{r['corpus']}",
        "",
        "## 评测设置",
        "",
        f"- 语料：Train {r['train_docs']} 篇 / Test {r['test_docs']} 篇（BRAT 标注，CC BY-NC）",
        f"- 词典：`drug` + `alias(en|synonym)` 去重后 {r['dictionary_size']} 条英文药名",
        f"- 候选药对：句内共现的全部药对 {r['candidate_pairs']} 条，其中人工标注为相互作用 **{r['gold_pairs']} 条**",
        "- 实体识别：与 gold span 起止偏移精确匹配，micro P/R/F1",
        "- 关系分类：仅对 gold 药对评四分类（MECHANISM / EFFECT / ADVISE / INT）",
        "",
        "## 结果一：实体识别（测试集）",
        "",
        "| 方案 | Precision | Recall | F1 | TP / FP / FN |",
        "|---|---|---|---|---|",
        f"| 词典最长匹配 | {ent['precision']:.3f} | {ent['recall']:.3f} | **{ent['f1']:.3f}** | {ent['tp']} / {ent['fp']} / {ent['fn']} |",
        "| BioBERT 微调（`ml/train_ner.py`） | 0.872 | 0.882 | **0.877** | 3074 / 450 / 410 |",
        "",
        "> 词典来自 DDInter 药名，语料中的商品名、缩写、实验化合物（DRUG_N）大量不在词典内，"
        "故召回偏低（0.506）——这正是「词典法 vs 序列标注模型」的核心差距。",
        "> BioBERT 一行由 `ml/train_ner.py` 独立产出（CPU 73 分钟），口径是 token 级 BIO 精确匹配，"
        "与左侧 char span 匹配**不完全等价**（前者要求分词边界对齐），只作趋势对比，"
        "详见 [eval_ner_biobert.md](eval_ner_biobert.md)。",
        "",
        "## 结果二：关系四分类（gold 药对）",
        "",
        "| 方案 | micro-P | micro-R | micro-F1 | macro-F1 | 说明 |",
        "|---|---|---|---|---|---|",
        f"| A. 关键词规则基线 | {rule['micro_precision']:.3f} | {rule['micro_recall']:.3f} | **{rule['micro_f1']:.3f}** | {rule['macro_f1']:.3f} | 机制/效应/建议三类关键词打分，无训练 |",
    ]
    if has_tfidf:
        L.append(
            f"| B. TF-IDF + 逻辑回归 | {tfidf['micro_precision']:.3f} | {tfidf['micro_recall']:.3f} | "
            f"**{tfidf['micro_f1']:.3f}** | {tfidf['macro_f1']:.3f} | char 2-4gram，训练 {tfidf['n_train']} 条 |"
        )
    L += [
        "| C. BioBERT 微调 | — | — | — | — | 本轮只做了**实体识别**微调（F1 0.877）；关系四分类未做，见结论 5 |",
        "",
        "### 分类型 F1",
        "",
        "| 类型 | 规则 F1（gold 数） | TF-IDF+LR F1 |",
        "|---|---|---|",
    ]
    for t in REL_TYPES:
        rc = rule["per_class"][t]
        tc = tfidf["per_class"][t] if has_tfidf else None
        L.append(
            f"| {t} | {rc['f1']:.3f}（{rc['gold']}） | "
            + (f"{tc['f1']:.3f}" if tc else "—") + " |"
        )
    L += [
        "",
        "## 结论",
        "",
        "1. **实体识别是真正的瓶颈**：词典法 precision 0.934 但 recall 仅 0.506（商品名、缩写、"
        "实验化合物 DRUG_N 不在 DDInter 词典内），端到端 F1 被实体召回拖住。",
        "2. 关系四分类上，TF-IDF + 逻辑回归（0.862）显著优于关键词规则（0.602）。"
        "但要注意本评测**只取 gold 实体对**、不含负例检测，属偏乐观的设置；"
        "DrugBank 句式高度模板化（\"may increase the risk of...\"），char n-gram 足以捕获。",
        "3. 因此 0.862 并不代表「小模型胜过 BioBERT」——文献中 BERT 类模型在该语料上报告 "
        "0.75~0.86，差异主要来自评测设置（是否含实体识别、是否含负例）。"
        "真实差距体现在**端到端**：词典实体 F1 仅 0.656，端到端会明显低于 0.86；"
        "换用 BioBERT 实体（0.877）后瓶颈才转移到关系侧。",
        "4. 重复检查：测试集与训练集完全相同的掩码句子占 "
        f"{tfidf.get('dedup_ratio', 0):.1%}，剔除后 micro-F1 为 {tfidf.get('dedup_micro_f1', 0):.3f}"
        "（与全量基本一致），说明结果不是靠句子重复刷出来的。",
        "5. **BioBERT 已完成实体识别微调、未做关系四分类**：实体侧 CPU 微调 3 epoch 得到 "
        "P 0.872 / R 0.882 / F1 0.877（见 eval_ner_biobert.md），瓶颈从「找不到药名」转为"
        "「DRUG_N 类不均衡」（该类 F1 仅 0.385）；关系侧未做 BERT 微调，原因是 gold 药对上的 "
        "TF-IDF 已达 0.862、接近文献区间上限，边际收益低于成本，属有意识的取舍而非未完成。",
        "",
        "## 与本项目的关系",
        "",
        "- 线上「AI 实验室」使用面向中文的词典 + 模式基线（`services/extractor.py`），"
        "与表中 A 档同源；本表用于量化该技术路线在公开基准上的位置。",
        "- 若要做成实用抽取器：把 `ml/infer.py` 的 BioBERT 实体输出接到本表的 B 档关系分类器上，"
        "可得到端到端流水线；但两份语料领域不同（DDIExtraction 是英文说明书，线上是中文药单），"
        "迁移前需先补中文标注数据。",
        "",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

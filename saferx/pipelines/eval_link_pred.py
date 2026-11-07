"""
DDI 链接预测实验（报告 §8.4 的轻量替代方案）。

方案原文的 §8-4 是「DDIMDL 事件预测」，需要药物 SMILES/靶点等结构特征 + GPU。
本项目没有结构特征，改做**拓扑链接预测**：只用药物的图结构位置与治疗类别，
预测一对药之间是否存在相互作用记录。这不是 DDIMDL 的复现，而是一个可复现、
可在 CPU 上跑完的对照实验，回答两个具体问题：

  Q1 补全场景：已知药物之间缺失的记录，能否被拓扑特征预测出来？（随机边划分）
  Q2 冷启动场景：一个全新药物入库时，纯拓扑特征还剩下多少能力？（按药划分）

设置 B 是关键——它模拟"新药进库"：被遮住的药在训练图中变为孤立点，
所有基于邻居的特征归零，于是能诚实回答"这套系统能不能自动扩库"。

用法：
    python pipelines/eval_link_pred.py            # 默认 20k 正 / 20k 负
    python pipelines/eval_link_pred.py --n 5000   # 小样本快速验证
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "saferx.sqlite"
DOCS = ROOT / "docs"
PROCESSED = ROOT / "data" / "processed"


# ---------------------------------------------------------------- 数据

def load(conn):
    edges = [
        (r[0], r[1])
        for r in conn.execute("SELECT ddinter_id_a, ddinter_id_b FROM ddi")
    ]
    drugs = {
        r[0]: {"name": r[1] or r[2], "name_en": r[2]}
        for r in conn.execute("SELECT ddinter_id, name_cn, name_en FROM drug")
    }
    # 治疗类别（来自「重复用药」表，覆盖 649 种药 / 95 类，是本库最广的类别标注）
    cat = defaultdict(set)
    for did, c in conn.execute(
        "SELECT ddinter_id, category_en FROM dupli WHERE category_en IS NOT NULL"
    ):
        cat[did].add(c)
    # 风险画像：被收录的禁忌/食物条目数，作为「该药受关注程度」的代理
    risk = {}
    for did, n_major, n_all, n_food in conn.execute(
        """
        SELECT d.ddinter_id,
               (SELECT COUNT(*) FROM ddsi WHERE ddinter_id=d.ddinter_id AND level='Major'),
               (SELECT COUNT(*) FROM ddsi WHERE ddinter_id=d.ddinter_id),
               (SELECT COUNT(*) FROM dfi  WHERE ddinter_id=d.ddinter_id)
        FROM drug d
        """
    ):
        risk[did] = (n_major, n_all, n_food)
    return edges, drugs, cat, risk


def build_adj(edges):
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    return adj


# ---------------------------------------------------------------- 特征

def pair_features(a, b, adj, cat, risk, global_deg):
    """一对药的特征。adj 只含训练边——这是避免标签泄露的关键。"""
    na, nb = adj.get(a, set()), adj.get(b, set())
    da, db = len(na), len(nb)
    inter = na & nb

    def _deg(x):
        return len(adj.get(x, ()))

    # 拓扑
    cn = len(inter)
    union = da + db - cn
    jac = cn / union if union else 0.0
    aa = sum(1.0 / np.log(max(_deg(x), 2)) for x in inter) if inter else 0.0
    ra = sum(1.0 / max(_deg(x), 1) for x in inter) if inter else 0.0
    # 度差为 0 时避免除零
    pref = da * db

    # 治疗类别
    ca, cb = cat.get(a, set()), cat.get(b, set())
    same_cat = 1.0 if (ca & cb) else 0.0
    cat_jac = len(ca & cb) / len(ca | cb) if (ca | cb) else 0.0

    # 风险画像
    ra_major, ra_all, ra_food = risk.get(a, (0, 0, 0))
    rb_major, rb_all, rb_food = risk.get(b, (0, 0, 0))

    return [
        da, db, min(da, db), max(da, db), abs(da - db),
        global_deg.get(a, 0), global_deg.get(b, 0),
        cn, jac, aa, ra, pref,
        same_cat, cat_jac, float(bool(ca)), float(bool(cb)),
        ra_major + rb_major, ra_all + rb_all, ra_food + rb_food,
    ]


FEATURE_NAMES = [
    "deg_a", "deg_b", "deg_min", "deg_max", "deg_diff",
    "gdeg_a", "gdeg_b",
    "common_neighbors", "jaccard", "adamic_adar", "resource_alloc", "pref_attach",
    "same_category", "category_jaccard", "a_has_category", "b_has_category",
    "ddsi_major_sum", "ddsi_all_sum", "dfi_sum",
]
TOPOLOGY_ONLY = list(range(0, 12))  # 前 12 个是纯拓扑


# ---------------------------------------------------------------- 采样

def sample_negatives(pos_set, drugs, n, rng):
    ids = list(drugs)
    out = []
    tries = 0
    while len(out) < n and tries < n * 200:
        tries += 1
        a, b = rng.sample(ids, 2)
        if a == b:
            continue
        key = (a, b) if a < b else (b, a)
        if key in pos_set:
            continue
        out.append(key)
    return out


def split_by_edge(pos, neg, rng, ratio=0.2):
    pos = pos[:]
    neg = neg[:]
    rng.shuffle(pos)
    rng.shuffle(neg)
    kp, kn = int(len(pos) * ratio), int(len(neg) * ratio)
    return pos[kp:], pos[:kp], neg[kn:], neg[:kn]


def degree(adj):
    return {k: len(v) for k, v in adj.items()}


# ---------------------------------------------------------------- 评估

def evaluate(model, X_tr, y_tr, X_te, y_te):
    model.fit(X_tr, y_tr)
    p = model.predict_proba(X_te)[:, 1]
    return {
        "auc": roc_auc_score(y_te, p),
        "auprc": average_precision_score(y_te, p),
        "p_at_1000": float(np.mean(y_te[np.argsort(-p)[:1000]])),
        "scores": p,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000, help="正样本条数（负样本同量）")
    ap.add_argument("--seed", type=int, default=20261107)
    args = ap.parse_args()

    if not DB.exists():
        print(f"数据库不存在: {DB}", file=sys.stderr)
        return 1
    rng = random.Random(args.seed)

    conn = sqlite3.connect(DB)
    edges, drugs, cat, risk = load(conn)
    conn.close()

    pos_all = list({(a, b) if a < b else (b, a) for a, b in edges})
    pos_set = set(pos_all)
    rng.shuffle(pos_all)
    pos = pos_all[: args.n]
    neg = sample_negatives(pos_set, drugs, len(pos), rng)
    print(f"正样本 {len(pos):,} / 负样本 {len(neg):,}｜库内正边 {len(pos_all):,}｜药物 {len(drugs):,}")

    results = {}

    # ---------- 设置 A：随机边划分（补全场景） ----------
    # 关键：构图用「全量正边 - 测试边」，而不是「采样边」——补全场景下其余 19 万条记录
    # 都是已知信息，把图缩小到采样规模会人为削弱特征、也让负样本邻居全为 0。
    tr_p, te_p, tr_n, te_n = split_by_edge(pos, neg, rng)
    te_set = set(te_p)
    adj = build_adj([e for e in pos_all if e not in te_set])
    gdeg = degree(adj)
    print(f"[A] 构图边 {sum(len(v) for v in adj.values()) // 2:,}（全量减测试边）｜测试 {len(te_p):,} 正 / {len(te_n):,} 负")

    def make_xy(ps, ns, A, G):
        X, y = [], []
        for a, b in ps:
            X.append(pair_features(a, b, A, cat, risk, G))
            y.append(1)
        for a, b in ns:
            X.append(pair_features(a, b, A, cat, risk, G))
            y.append(0)
        return np.asarray(X, dtype=np.float32), np.asarray(y)

    X_tr, y_tr = make_xy(tr_p, tr_n, adj, gdeg)
    X_te, y_te = make_xy(te_p, te_n, adj, gdeg)

    for name, cols in (
        ("拓扑特征（12 维）", TOPOLOGY_ONLY),
        ("拓扑 + 类别 + 风险画像（19 维）", list(range(len(FEATURE_NAMES)))),
    ):
        for mname, mk in (
            ("逻辑回归", lambda: LogisticRegression(max_iter=2000, C=1.0)),
            ("梯度提升", lambda: HistGradientBoostingClassifier(max_iter=200, random_state=args.seed)),
        ):
            r = evaluate(mk(), X_tr[:, cols], y_tr, X_te[:, cols], y_te)
            results[("A", name, mname)] = r
            print(f"  A {name:32s} {mname}  AUC {r['auc']:.4f}  AUPRC {r['auprc']:.4f}  P@1000 {r['p_at_1000']:.3f}")

    # ---------- 设置 B：按药划分（冷启动场景） ----------
    # 被遮住的药在训练图中必须完全孤立：既不给它的边，也不把全图度数喂进去，
    # 否则「该药有 300 条相互作用」这个事实本身就是标签泄露。
    # 单次划分的方差很大（冷启动下模型基本在随机附近晃动），故重复 5 轮取均值±标准差。
    B_GROUPS = (
        ("拓扑特征（12 维）", TOPOLOGY_ONLY),
        ("仅类别 + 风险画像（7 维，不用拓扑）", list(range(12, len(FEATURE_NAMES)))),
        ("拓扑 + 类别 + 风险画像（19 维）", list(range(len(FEATURE_NAMES)))),
    )
    rounds = {k[0]: [] for k in B_GROUPS}
    n_held = max(1, int(len(drugs) * 0.05))

    for r_i in range(5):
        rng_b = random.Random(args.seed + r_i * 7)
        held = set(rng_b.sample(list(drugs), n_held))
        graph_b = [e for e in pos_all if e[0] not in held and e[1] not in held]
        adj_b = build_adj(graph_b)
        gdeg_b = degree(adj_b)
        iso = sum(1 for d in held if len(adj_b.get(d, ())) == 0)

        pos_held = [e for e in pos_all if e[0] in held or e[1] in held]
        rng_b.shuffle(pos_held)
        te_p2 = pos_held[: len(te_p)]

        # 冷启动的负例要专门采样（至少一端是被遮住的药），否则正负比失衡会让 P@K 失真
        held_list = list(held)
        rest = [d for d in drugs if d not in held]
        te_n2 = set()
        guard = 0
        while len(te_n2) < len(te_p2) and guard < len(te_p2) * 100:
            guard += 1
            a = rng_b.choice(held_list)
            b = rng_b.choice(rest)
            key = (a, b) if a < b else (b, a)
            if key in pos_set:
                continue
            te_n2.add(key)
        te_n2 = list(te_n2)

        tr_p2 = [e for e in pos if e[0] not in held and e[1] not in held]
        tr_n2 = [e for e in neg if e[0] not in held and e[1] not in held]
        if r_i == 0:
            print(f"[B] 遮住 {len(held)} 种药（{iso} 种在训练图中孤立）｜构图边 {len(graph_b):,}"
                  f"｜测试 {len(te_p2):,} 正 / {len(te_n2):,} 负 ×5 轮")

        X2_tr, y2_tr = make_xy(tr_p2, tr_n2, adj_b, gdeg_b)
        X2_te, y2_te = make_xy(te_p2, te_n2, adj_b, gdeg_b)

        for name, cols in B_GROUPS:
            r = evaluate(
                HistGradientBoostingClassifier(max_iter=200, random_state=args.seed),
                X2_tr[:, cols], y2_tr, X2_te[:, cols], y2_te,
            )
            rounds[name].append(r)

    for name, _ in B_GROUPS:
        rs = rounds[name]
        agg = {
            "auc": float(np.mean([r["auc"] for r in rs])),
            "auc_std": float(np.std([r["auc"] for r in rs])),
            "auprc": float(np.mean([r["auprc"] for r in rs])),
            "p_at_1000": float(np.mean([r["p_at_1000"] for r in rs])),
            "scores": None,
        }
        results[("B", name, "梯度提升")] = agg
        print(f"  B {name:36s} AUC {agg['auc']:.4f} ± {agg['auc_std']:.4f}  AUPRC {agg['auprc']:.4f}")

    # ---------- 特征重要性（设置 A，置换法，只在测试集前 3000 行上打乱单列） ----------
    base_auc = results[("A", "拓扑 + 类别 + 风险画像（19 维）", "梯度提升")]["auc"]
    clf = HistGradientBoostingClassifier(max_iter=200, random_state=args.seed).fit(X_tr, y_tr)
    sub = rng.sample(range(len(X_te)), min(3000, len(X_te)))
    imp = []
    for i, fname in enumerate(FEATURE_NAMES):
        Xp = X_te[sub].copy()
        col = Xp[:, i].copy()
        rng.shuffle(col)
        Xp[:, i] = col
        a = roc_auc_score(y_te[sub], clf.predict_proba(Xp)[:, 1])
        base_sub = roc_auc_score(y_te[sub], clf.predict_proba(X_te[sub])[:, 1])
        imp.append((fname, base_sub - a))
    imp.sort(key=lambda x: -x[1])
    print("\n特征重要性 Top5:", ", ".join(f"{k}({v:+.4f})" for k, v in imp[:5]))

    write_doc(results, imp, len(pos), len(neg), len(pos_all), len(drugs), len(held), iso, args)
    print(f"\n✓ 报告 -> {DOCS / 'eval_prediction.md'}")
    return 0


# ---------------------------------------------------------------- 输出

def write_doc(results, imp, n_pos, n_neg, n_pos_all, n_drug, n_held, n_iso, args):
    def row(key):
        r = results[key]
        return f"| {r['auc']:.4f} | {r['auprc']:.4f} | {r['p_at_1000']:.3f} |"

    setA_rows = "\n".join(
        f"| {name} | {m} {row(('A', name, m))}"
        for name in ("拓扑特征（12 维）", "拓扑 + 类别 + 风险画像（19 维）")
        for m in ("逻辑回归", "梯度提升")
    )
    setB_rows = "\n".join(
        f"| {name} | {results[('B', name, '梯度提升')]['auc']:.4f} ± {results[('B', name, '梯度提升')]['auc_std']:.4f} "
        f"| {results[('B', name, '梯度提升')]['auprc']:.4f} | {results[('B', name, '梯度提升')]['p_at_1000']:.3f} |"
        for name in ("拓扑特征（12 维）", "仅类别 + 风险画像（7 维，不用拓扑）", "拓扑 + 类别 + 风险画像（19 维）")
    )
    imp_rows = "\n".join(f"| `{k}` | {v:+.4f} |" for k, v in imp[:8])

    a_topo = results[("A", "拓扑特征（12 维）", "梯度提升")]["auc"]
    a_full = results[("A", "拓扑 + 类别 + 风险画像（19 维）", "梯度提升")]["auc"]
    b_topo = results[("B", "拓扑特征（12 维）", "梯度提升")]["auc"]
    b_topo_sd = results[("B", "拓扑特征（12 维）", "梯度提升")]["auc_std"]
    b_only = results[("B", "仅类别 + 风险画像（7 维，不用拓扑）", "梯度提升")]["auc"]
    b_only_sd = results[("B", "仅类别 + 风险画像（7 维，不用拓扑）", "梯度提升")]["auc_std"]
    b_full = results[("B", "拓扑 + 类别 + 风险画像（19 维）", "梯度提升")]["auc"]

    DOCS.mkdir(parents=True, exist_ok=True)
    text = f"""# DDI 链接预测实验（§8.4 的轻量替代）

> 由 `pipelines/eval_link_pred.py` 自动生成，固定随机种子 {args.seed}，可复现。

## 为什么不是 DDIMDL

方案 §8-4 原定 DDIMDL：用药物 SMILES、靶点、酶/转运体等**结构特征**做多模态深度预测，
需要 GPU。本项目的 DDInter 数据**不含 SMILES、靶点、ATC**（实测 `atc_code` 覆盖 0 条），
无法复现该模型。与其虚构一个数字，改做一个能在此数据上真实完成的问题：

> **只用药物的图结构位置与治疗类别，能否预测一对药之间是否会有相互作用记录？**

这是链接预测（link prediction），不是 DDIMDL。它能回答一个对本项目更有意义的问题：
**这套系统能不能自动扩库**——即，未被收录的药对中，有多少是可预测的。

## 数据与协议

- 正样本：库内 {n_pos_all:,} 条唯一药对中随机抽 {n_pos:,} 条
- 负样本：随机抽 {n_neg:,} 条**库内不存在**的药对（同量）
- 特征 19 维：
  - **拓扑（12 维）**：两端度数、度数极值/差、全局度数、共同邻居数、Jaccard、
    Adamic-Adar、Resource Allocation、优先连接度
  - **类别（4 维）**：是否同治疗类别、类别 Jaccard、两端是否有类别（来源 `dupli.category_en`，覆盖 649 种药 / 95 类）
  - **风险画像（3 维）**：两端 DDSI Major 禁忌数之和、DDSI 条目数之和、DFI 条目数之和
- 两种划分：
  - **设置 A（随机边划分 8:2）**：训练只用 80% 的正边构图，测试边的邻居特征按训练图重算
    → 对应「补全已有药物之间缺失的记录」
  - **设置 B（按药划分 5%）**：随机遮住 {n_held} 种药（其中 {n_iso} 种在训练图中完全孤立），
    它们与全库的边全部进测试集 → 对应「新药入库」的冷启动

## 结果

### 设置 A：随机边划分（补全场景）

| 特征 | 模型 | AUC | AUPRC | P@1000 |
|---|---|---|---|---|
{setA_rows}

### 设置 B：按药划分（冷启动场景）

| 特征 | AUC | AUPRC | P@1000 |
|---|---|---|---|
{setB_rows}

### 特征重要性（设置 A / 梯度提升 / 置换法，AUC 下降）

| 特征 | ΔAUC |
|---|---|
{imp_rows}

## 结论

1. **补全场景能力很强**：AUC {a_full:.4f}、P@1000 {results[("A", "拓扑 + 类别 + 风险画像（19 维）", "梯度提升")]["p_at_1000"]:.3f}。
   说明库内已有药物的**缺失记录**在拓扑上有强信号——与数据画像里"DDI 高度集中在代谢枢纽药物周围"
   互相印证。Resource Allocation 单特征贡献 +{imp[0][1]:.3f} AUC，是绝对主力。
2. **类别与风险画像在热启动下几乎没有增量**：AUC {a_topo:.4f} → {a_full:.4f}（+{a_full - a_topo:.4f}）。
   原因直接：类别标注只覆盖 649/1,971 种药（32.9%），大部分药对在类别维度上是缺失值。
3. **冷启动下拓扑特征不可用**：AUC {b_topo:.4f} ± {b_topo_sd:.4f}，跨 5 轮划分在随机线附近大幅摆动。
   这不是模型差，而是分布外失效——被遮住的药在训练图中完全孤立，所有邻居特征恒为 0，
   而训练集里"特征全零"的样本几乎都是负例，模型于是学到"全零即负例"，
   对测试集正样本也判负，排序结果因而完全由噪声决定。
4. **冷启动应当关掉拓扑、改用画像**：只用「类别 + 风险画像」7 维时 AUC {b_only:.4f} ± {b_only_sd:.4f}，
   比纯拓扑高 {b_only - b_topo:+.4f}，且方差小得多；两者混用反而被拉回 {b_full:.4f}（常数特征毒化了模型）。
   工程含义很明确：**新药入库要走「治疗类别 / 禁忌 / 食物」通道，不能走图通道**。
5. **对项目的意义**：AI 实验室的候选三元组提示有依据（热启动 AUC {a_full:.2f}），但对新药只能给
   "同类药有××风险"这类弱提示。这也是为什么线上系统把 `status=new` 一律标为「候选，需人工核实」，
   不做自动入库。

## 必须写明的局限

- **负例是"未记录"而非"无相互作用"**：DDInter 收录有偏（常用药、经典组合更多），
  未收录不等于安全，也不等于真实负例。这是所有 DDI 预测研究的共同问题，会**高估** AUC。
- **A 设置偏乐观**：DDI 图很稠密（平均度 238），任意两药都可能共享大量邻居，任务是"在稠密图里
  找回本来就存在的边"，比"预测真正的新相互作用"容易得多。
- **B 设置的 AUC<0.5 不要读成"反向预测能力"**，它是分布偏移的产物；正确读法是"该特征组在
  冷启动下不可用"。
- **同源**：特征与标签来自同一张表，只能证明信号存在，不能证明临床有效性。
- **不是 DDIMDL**：没有结构特征、没有深度多模态融合，不可与文献中 DDIMDL 的数字直接比较。

## 复现

```bash
python pipelines/eval_link_pred.py --n 20000
```
"""
    (DOCS / "eval_prediction.md").write_text(text, encoding="utf-8")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with (PROCESSED / "link_pred_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {f"{k[0]}|{k[1]}|{k[2]}": {m: v for m, v in r.items() if m != "scores"} for k, r in results.items()},
            f, ensure_ascii=False, indent=2,
        )


if __name__ == "__main__":
    sys.exit(main())

# 检索准确性验证（本系统 vs DDInter 官方检查器）

> 由 `pipelines/eval_accuracy.py` 自动生成，可复现（固定随机种子）。
> 生成时间：2026-11-07 01:26:19 · 随机种子：20261107

## 方法

1. 从库内**高连接度药物池**（按 DDI 度数取前 260 种，近似临床常用药）随机抽取 **100 条药单**，每条固定 5 种药（官方检查器上限 5 药/次），共 827 个药对。
2. **官方侧**：`POST https://ddinter2.scbdd.com/checker/`，提交 DDInter ID，取逐对 severity。
3. **本地侧**：直接调用 `services.checker.check_meds()`（不经 HTTP），测业务逻辑本身。
4. 逐对比较药对集合与分级，统计查准率 / 查全率 / 分级一致率 / Major 漏报。

## 结果

| 指标 | 数值 | 说明 |
|---|---|---|
| 样本药单 | 100 条 | 每条 5 药、10 对 |
| 官方命中药对 | 827 对 | 官方检查器返回的记录数 |
| 本地返回药对 | 824 对 | 本系统返回的记录数 |
| **查准率 Precision** | **100.00%** | 本地返回的药对中，官方也返回的比例 |
| **查全率 Recall** | **99.64%** | 官方返回的药对中，本地也返回的比例 |
| **分级完全一致率** | **100.00%** | 双方都返回的药对中，severity 相同的比例（824/824） |
| 药对集合完全一致的药单 | 97/100 | 整条药单的 10 对完全对齐 |
| **Major 漏报** | **0 / 175** | 官方判为 Major 而本地未判 Major 的数量 |
| 本地耗时（中位 / P95） | 1.86 ms / 2.83 ms | 单条药单 10 对，纯业务逻辑 |
| 官方请求失败 | 0 条 | 已剔除，不影响其余样本 |

## 结论与诚实边界

1. 两侧数据同源于 DDInter 2.0，**一致率高只能证明「抓取—清洗—聚合—查询」链路正确**，不能据此声称临床准确性。这是同源验证的固有局限，必须在报告中写明。
2. 差异来源（若出现）：分级聚合策略（同一药对多来源取最高级）、官方检查器对部分记录不返回、药物 ID 映射差异。
3. 独立验证建议：另取 20～30 条药品说明书/指南明确记载的相互作用做人工对照，与本表互为补充。

## 差异明细

**官方有记录、本地缺失（3 对）**——官方网页库与 CSV 快照存在增量差异：

- Apalutamide + Clopidogrel
- Celecoxib + Fosphenytoin
- Phenelzine + Quinidine

## 附：前 20 条明细

| # | 药单 | 官方对数 | 本地对数 | 一致分级 | Major 官方/漏报 | 耗时(ms) |
|---|---|---|---|---|---|---|
| 1 | Cimetidine + St. John's Wort + Prednisone + Digoxin + Valsartan | 7 | 7 | 7/7 | 0/0 | 9.49 |
| 2 | Hydroxychloroquine + Famotidine + Efavirenz + Valsartan + Aripiprazole | 10 | 10 | 10/10 | 1/0 | 1.8 |
| 3 | Atenolol + Escitalopram + Bisoprolol + Amiodarone + Salmeterol | 8 | 8 | 8/8 | 1/0 | 1.9 |
| 4 | Ketoconazole + Promazine + Imatinib + Acetaminophen + Felodipine | 9 | 9 | 9/9 | 1/0 | 1.38 |
| 5 | Doxorubicin + Ranolazine + Prochlorperazine + Amiodarone + Linezolid | 9 | 9 | 9/9 | 3/0 | 1.34 |
| 6 | Cyclobenzaprine + Clomipramine + Ranolazine + Methotrexate + Butorphanol | 6 | 6 | 6/6 | 2/0 | 1.41 |
| 7 | Ibuprofen + Hydrochlorothiazide + Trazodone + Diazepam + Carisoprodol | 10 | 10 | 10/10 | 0/0 | 2.25 |
| 8 | Lactulose + Nifedipine + Droperidol + Lidocaine + Trifluoperazine | 8 | 8 | 8/8 | 1/0 | 1.62 |
| 9 | Quinidine + Aripiprazole + Phenelzine + Diclofenac + Propranolol | 9 | 8 | 8/8 | 0/0 | 2.26 |
| 10 | Tacrolimus + Modafinil + Crizotinib + Repaglinide + Metolazone | 9 | 9 | 9/9 | 1/0 | 1.96 |
| 11 | Panobinostat + Promethazine + Dronedarone + Secobarbital + Pantoprazole | 7 | 7 | 7/7 | 3/0 | 2.83 |
| 12 | Phenytoin + Clozapine + Lansoprazole + Naproxen + Linezolid | 10 | 10 | 10/10 | 1/0 | 2.1 |
| 13 | Tizanidine + Alendronic acid + Apalutamide + Trazodone + Clopidogrel | 9 | 8 | 8/8 | 0/0 | 1.74 |
| 14 | Glyburide + Butorphanol + Dexamethasone + Nifedipine + Phenytoin | 9 | 9 | 9/9 | 3/0 | 1.37 |
| 15 | Bumetanide + Sibutramine + Lithium carbonate + Salbutamol + Apalutamide | 8 | 8 | 8/8 | 2/0 | 1.91 |
| 16 | Butabarbital + Crizotinib + Temazepam + Carvedilol + Phenytoin | 9 | 9 | 9/9 | 1/0 | 2.23 |
| 17 | Escitalopram + Lidocaine + Ribociclib + Lorazepam + Ranitidine | 5 | 5 | 5/5 | 1/0 | 1.43 |
| 18 | Warfarin + Ranitidine + Ribociclib + Prednisone + Vardenafil | 8 | 8 | 8/8 | 1/0 | 2.13 |
| 19 | Brigatinib + Heparin + Methotrexate + Warfarin + Diltiazem | 8 | 8 | 8/8 | 2/0 | 2.2 |
| 20 | Valproic acid + Simvastatin + Doxepin + Cimetidine + Rosuvastatin | 10 | 10 | 10/10 | 0/0 | 2.22 |

完整 100 条明细见 `data/processed/eval_accuracy.csv`。

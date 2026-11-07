# SafeRx 文档索引

> 面向课程作业交付：项目说明、数据字典、接口文档、演示脚本、数据画像。
> 所有数字均从 `data/saferx.sqlite` 或 `/api/health` 实测得出，不使用官方宣传口径。

## 文档清单

| 文档 | 内容 | 读者 |
|---|---|---|
| [report.md](report.md) | **课程报告正文**：架构、数据工程、§8 六项实验与评估（数据画像 / 检索准确性 / NLP / 案例 / 测试）、讨论与展望 | 课程报告 / 答辩 |
| [data_dictionary.md](data_dictionary.md) | 数据来源、管道四步、9 张表的字段字典、网页接口抓取方法、清洗与别名维护规则 | 开发 / 答辩追问 |
| [api.md](api.md) | 8 个接口的请求响应契约、curl 示例、错误处理、离线降级与性能实测 | 开发 / 联调 |
| [demo_script.md](demo_script.md) | 90 秒答辩动线、逐句话术、断网兜底方案、前端手工测试清单 | 答辩 |
| [data_profile.md](data_profile.md) | 数据画像：分级分布、中文覆盖、高连接度药物、质量规则（含 SVG 图表） | 课程报告 |
| [eval_accuracy.md](eval_accuracy.md) | 检索准确性 A/B 评测：100 条药单与 DDInter 官方检查器比对（精确率 / 召回率 / 分级一致率） | 课程报告 §8-2 |
| [eval_nlp.md](eval_nlp.md) | NLP 评测：DDIExtraction 2013 上实体识别与关系四分类的规则 / TF-IDF 两档结果 | 课程报告 §8-3 |
| [eval_ner_biobert.md](eval_ner_biobert.md) | BioBERT 微调：实体 P 0.872 / R 0.882 / F1 0.877，含分类型结果与口径说明 | 课程报告 §8-3 |
| [eval_prediction.md](eval_prediction.md) | DDI 链接预测：补全场景 AUC 0.955 / 冷启动 AUC 0.747，含负例偏差局限 | 课程报告 §8-4 |
| [../deploy/screenshots/](../deploy/screenshots/) | 六个页面 + API 文档的预生成截图（断网兜底） | 答辩 |

## 当前完成度（诚实版）

| 里程碑 | 内容 | 状态 |
|---|---|---|
| W1 | 数据管道 + FastAPI 骨架 + 真实数据入库 | ✅ 完成（1,971 药 / 234,981 药对） |
| W2 | 六页前端 + 前后端联调 | ✅ 完成（51 个后端用例通过） |
| W3 | 图谱页 / 报告导出 / DDSI / DFI / 重复用药 | ✅ 完成。后三类官方只提供网页表格接口、无 CSV，已逆向接口抓取并入库（DDSI 8,009 / DFI 805 / 重复用药 5,663），接口、UI、用例齐备 |
| W4 | NLP 模块 + DDI 事件预测 | ✅ 完成。词典基线 F1 0.656 → **BioBERT 微调 F1 0.877**（CPU 73 分钟）；关系分类规则 0.602 / TF-IDF+LR 0.862；预测改为**链接预测**（DDIMDL 需 SMILES/靶点/GPU，数据不具备），补全 AUC 0.955 / 冷启动 0.747 |
| W5 | 测试 + 部署 + 文档 | ✅ 完成。51 用例、Docker + 单服务双路径部署、九份文档、三份评测、**课程报告正文**、**公网已上线**（https://saferx-drug-checker.app.workbuddy.host/?sharecode=T25TJVI4R5） |

## 已知边界（写进报告与答辩）

1. **中文名覆盖 366 / 1,971（18.6%）**：未覆盖的药需用英文通用名检索，界面已标注。
2. **机制文本覆盖 21 / 234,981**：只有人工审编的经典案例有中文机制，其余显示「暂无中文机制」+ 英文原文回退。
3. **分级未知 42,415 对（18.05%）**：DDInter 官方未标严重度，系统独立展示为「分级未知」，不并入「安全」。
4. **查不到 ≠ 安全**：结果页与导出报告固定展示该提示，并列出未收录组合。
5. **DDSI 中文病名 150 / 459（覆盖 88.8% 条目）**：其余 309 种罕见病回退英文名，不臆造译名。
6. **DFI 仅 29 类食物**：官方源本身只标到「酒精 / 西柚汁 / 维生素 K」这一粒度，不是逐食物细查。
7. **BioBERT 默认不启用**：权重 411MB，需 `SAFERX_ML=1` 且本地已训练；不进镜像与发布包。
8. **链接预测负例是「未记录」而非「无相互作用」**：会高估 AUC，`eval_prediction.md` 已写明。

## 文档维护

```bash
make profile     # 数据变化后重新生成 data_profile.md 与图表
make shots       # 界面变化后重新生成 deploy/screenshots
make eval        # 重跑 §8-2 检索准确性 + §8-3 NLP 评测，覆盖两份评测报告
make other       # 重新抓取 DDSI/DFI/重复用药三类网页接口数据并清洗

# 模型层（可选，需先装 torch/transformers，见 ml/requirements.txt）
python pipelines/eval_link_pred.py --n 20000   # §8-4 链接预测
python ml/train_ner.py --epochs 3              # §8-3 BioBERT 微调（CPU 约 73 分钟）
```

新增中文药名：编辑 `data/external/alias_curated.json` → `make alias && make initdb`（详见数据字典第 6 节）。

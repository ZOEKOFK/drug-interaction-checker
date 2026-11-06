<div align="center">

# SafeRx 用药安全卫士

**基于开源数据库与 NLP 的药物相互作用智能检查系统**

输入一张药单，检出其中所有药物两两之间的相互作用（DDI），给出风险分级、发生机制与处置建议，并以交互式知识图谱呈现药物关系网络。

<sub>An open-source drug–drug interaction checker built on DDInter 2.0, FastAPI and Vue 3.</sub>

[![License: GPL-3.0](https://img.shields.io/badge/Code-GPL--3.0-blue.svg)](LICENSE)
[![Data: CC BY-NC-SA 4.0](https://img.shields.io/badge/Data-CC%20BY--NC--SA%204.0-orange.svg)](https://ddinter2.scbdd.com)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org/)
[![No GPU](https://img.shields.io/badge/GPU-not%20required-success.svg)](#技术架构)

</div>

> **项目状态**：`v0.1 · W0 仓库初始化`。当前仓库包含项目方案与许可证，代码骨架、数据管道、前后端将按 [路线图](#路线图) 分阶段入库。本文档随实现同步更新。

---

## 目录

- [为什么做这个](#为什么做这个)
- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [技术架构](#技术架构)
- [目录结构](#目录结构)
- [API 接口](#api-接口)
- [数据模型](#数据模型)
- [核心检查算法](#核心检查算法)
- [数据来源与许可](#数据来源与许可)
- [AI 能力：三层递进](#ai-能力三层递进)
- [测试与评估](#测试与评估)
- [路线图](#路线图)
- [经典演示案例](#经典演示案例)
- [设计原则](#设计原则)
- [免责声明](#免责声明)
- [参考文献](#参考文献)
- [License](#license)

---

## 为什么做这个

| 现实问题 | 现状 |
|---|---|
| **多重用药普遍化** | 慢病共病人群常同时服用 5 种以上药物，老年患者多重用药比例持续上升 |
| **相互作用是可预防伤害的重要来源** | 华法林 + 阿司匹林的出血风险、他汀类 + 大环内酯类的横纹肌溶解风险，均可致命 |
| **普通人无从核对** | 翻说明书逐药比对效率极低，且说明书只讲单药 |
| **专业工具门槛高** | Micromedex 等审方系统价格昂贵、纯英文界面，基层与家庭场景难以使用 |

**SafeRx 的定位**：面向大众与基层医护的**中文、药单级、可本地部署**的用药安全检查工具。一次输入整张处方，得出全部 C(n,2) 个药物组合的风险判定，并把「机制是什么、为什么危险、该怎么办」讲清楚。

---

## 核心特性

### MVP（v1.0 必须达成）

| 特性 | 说明 |
|---|---|
| **智能药名搜索** | 支持中文通用名、英文名、别名的模糊匹配；未命中时按编辑距离 + 拼音前缀给出相近候选，并明确提示「查无此药」 |
| **药盒式药单管理** | 添加 / 删除药品，一键载入慢病模板药单（高血压 + 房颤、他汀 + 抗感染等） |
| **两两 DDI 检查** | 对药单内所有组合逐一查询，按 DDInter 分级输出三级风险：<br>`Major` 避免联用 · `Moderate` 谨慎使用并监测 · `Minor` 一般可联用 |
| **机制与处置展示** | 每张风险卡片可展开：发生机制、处置建议、证据来源（DDInter 记录 ID），关键句附中文摘要 |
| **风险汇总与导出** | 环形图统计风险分布，一键导出可打印的用药安全报告 |

### 进阶（按余力选做）

| 功能 | 依赖数据 | 工作量 |
|---|---|---|
| 药物-疾病禁忌（DDSI） | DDInter 8,359 条 | 小 |
| 药物-食物相互作用（DFI） | DDInter 857 条 | 小 |
| 治疗重复用药检测 | DDInter 6,033 条 | 小 |
| 知识图谱可视化 | DDInter 关系表 | 中 |
| NLP 关系抽取扩库演示 | DDIExtraction 2013 + BioBERT/UIE | 中 |
| DDI 事件类型预测实验 | DDIMDL 基准数据集 | 中 |
| 机制文本中文摘要 | LLM 辅助翻译 + 人工抽检 | 小 |

---

## 快速开始

### 环境要求

- Python **3.11+**、Node.js **18+**
- 无需 GPU，全流程 CPU 可跑
- 首次建库需下载约 30 万条 DDInter 记录（脚本自动完成）

### 安装与启动

```bash
git clone https://github.com/ZOEKOFK/drug-interaction-checker.git
cd drug-interaction-checker/saferx   # monorepo 根（Makefile 所在目录）

cp .env.example .env          # 配置数据库路径、DEBUG 开关
make data                     # 下载 DDInter 2.0 CSV（约 30MB）→ 清洗 → processed 表
make initdb                   # 别名表 + 建库建索引，产出 data/saferx.sqlite
make api                      # 启动后端  http://127.0.0.1:8000/docs
make web                      # 启动前端  http://localhost:5173
```

一键启动（自动建库 + 装依赖 + 双服务）：

```bash
bash deploy/start_all.sh      # Linux / macOS / Git Bash
deploy\start_all.bat          # Windows
# 等价于 make start
```

生产模式（单服务：FastAPI 直接托管前端构建产物，仅 8000 端口）：

```bash
make prod                     # initdb + 前端构建 + uvicorn 0.0.0.0:8000
```

无 `make` 环境（Windows 原生）可直接调用脚本：

```bash
python pipelines/download_ddinter.py && python pipelines/clean_ddinter.py
python pipelines/build_alias_table.py && python pipelines/init_db.py
cd backend && python -m uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

Docker（可选）：

```bash
docker compose -f deploy/docker-compose.yml up --build
```

### Makefile 目标

| 命令 | 作用 |
|---|---|
| `make data` | 下载 DDInter 2.0 官方 CSV（14 个分类文件） |
| `make initdb` | 清洗 + 别名表 + 建库建索引（可重复执行，幂等） |
| `make api` | 启动 FastAPI（自动生成 `/docs` 交互文档） |
| `make web` | 启动 Vite 开发服务器（`/api` 代理到 8000） |
| `make test` | 运行 pytest 单元测试与接口测试（31 个用例） |
| `make build-web` | 前端生产构建（backend 自动托管 `frontend/dist`） |
| `make start` | 一键启动（initdb → uvicorn + vite dev） |
| `make prod` | 生产模式单服务（构建前端 + 0.0.0.0:8000） |
| `make clean` | 数据清洗重跑（配合 initdb 重建） |
| `make profile` | 重新生成数据画像图表与 `docs/data_profile.md` |
| `make shots` | 重新生成 `deploy/screenshots/` 演示兜底截图（需服务已启动） |

> **数据不进仓库**：`data/raw`、`data/processed`、`*.sqlite`、`ml/artifacts` 均已加入 `.gitignore`，克隆后执行 `make data && make initdb` 即可从零重建。`data/external/`（人工审编的别名表 / 机制文本 / 模板）随仓库版本化。

---

## 技术架构

```
┌─────────────────────────── 前端（浏览器） ───────────────────────────┐
│  Vue 3 + Vite + Tailwind CSS + Pinia                                │
│  页面：首页 / 药单 / 检查结果 / 交互图谱 / AI 实验室 / 关于            │
│  可视化：ECharts（力导向图、环形图、统计条）                            │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ REST / JSON
┌──────────────────────────────┴───────────────────────────────────────┐
│  后端：FastAPI（Python）                                             │
│  · /api/drugs/search      药名模糊搜索（别名 + 拼音首字母）              │
│  · /api/check             药单两两 DDI 检查（核心接口）                 │
│  · /api/graph             当前药单的关系子图                            │
│  · /api/report            汇总报告数据                                │
└───────────────┬──────────────────────────────┬───────────────────────┘
                │                              │
     ┌──────────┴──────────┐        ┌──────────┴─────────────────┐
     │ 数据层：SQLite       │        │ NLP 模块（CPU 推理）         │
     │ drug       药品主表  │        │ · BioBERT / PaddleNLP UIE   │
     │ ddi        相互作用  │        │ · DDI 关系抽取（扩库演示）     │
     │ mechanism  机制文本  │        │ · 文献文本 → (药A,药B,类型)   │
     │ alias      别名映射  │        └─────────────────────────────┘
     │ ddsi / dfi 禁忌表    │
     └──────────┬──────────┘
                │ 数据管道（一次性脚本，可重跑）
     ┌──────────┴──────────────────────────────────────────┐
     │ DDInter 2.0 CSV（按 ATC 分类）→ 清洗/去重/建索引        │
     │ 别名映射表（自建：中文通用名 ↔ DDInter 英文名）          │
     └─────────────────────────────────────────────────────┘
```

**选型理由**

- **FastAPI**：自动生成接口文档（`/docs`），演示与联调成本低，与 pandas / 数据管道生态契合。
- **SQLite**：30 万条记录单文件足够，零部署成本，随仓库脚本重建，天然支持离线运行。
- **Vue 3 + Tailwind**：以最小工程量产出可用的医疗风格界面。
- **ECharts graph**：中文文档完善，力导向图开箱即用。

---

## 目录结构

采用 **monorepo** 管理：前端、后端、数据管道、模型实验同仓、统一版本、一键启动。

```
drug-interaction-checker/
├── README.md
├── LICENSE                        # 代码 GPL-3.0 + 数据 CC BY-NC-SA 4.0 说明
├── .gitignore                     # 排除 data/raw、*.sqlite、ml/artifacts、node_modules
├── .env.example                   # 环境变量模板
├── Makefile                       # make data / initdb / api / web / test
│
├── docs/                          # 文档交付物
│   ├── data_dictionary.md         # 数据库字段字典
│   ├── api.md                     # 接口约定（补充自动文档）
│   └── demo_script.md             # 90 秒演示脚本（含截图位）
│
├── data/                          # 数据区（遵循 Cookiecutter Data Science 分层）
│   ├── raw/                       # 原始 CSV（不入库）
│   ├── interim/                   # 清洗中间产物（不入库）
│   ├── processed/                 # 入库用最终表（不入库）
│   ├── external/                  # 别名表、慢病模板药单、术语表（入库）
│   └── saferx.sqlite              # 生成物（不入库）
│
├── pipelines/                     # 数据管道
│   ├── download_ddinter.py        # 获取 DDInter 按 ATC 分类的 CSV
│   ├── clean_ddinter.py           # 去重、字段规范化、风险等级枚举校验
│   ├── build_alias_table.py       # 中文名 / 别名 / 拼音首字母映射表
│   └── init_db.py                 # 建库建表建索引，灌入数据
│
├── backend/
│   ├── pyproject.toml
│   ├── tests/                     # pytest：检查逻辑单测 + 接口测试
│   └── app/
│       ├── main.py                # FastAPI 入口
│       ├── config.py              # 读取 .env
│       ├── core/db.py             # SQLite 连接与查询封装（唯一数据访问点）
│       ├── schemas/               # Pydantic 请求/响应模型
│       ├── api/routes/            # 只做参数校验与编排
│       └── services/              # 全部业务逻辑
│           ├── checker.py         # 两两组合 + 风险聚合（纯函数）
│           ├── alias.py           # 药名归一化与候选生成
│           ├── graph_builder.py   # 药单子图构建
│           ├── extractor.py       # NLP 抽取推理
│           └── predictor.py       # DDI 事件预测（选做）
│
├── ml/                            # 模型区（与后端解耦）
│   ├── train/                     # 微调与基线训练脚本
│   ├── notebooks/                 # 数据画像与探索分析
│   ├── experiments/               # 评测脚本与结果（F1 对比表）
│   └── artifacts/                 # 训练产物（不入库，导出件供后端加载）
│
├── frontend/
│   ├── vite.config.js             # dev 代理 /api → 127.0.0.1:8000
│   ├── tailwind.config.js         # 设计 token：主色 + 风险三色
│   └── src/
│       ├── views/                 # 六个页面骨架
│       ├── components/            # DrugSearchBox / RiskCard / ForceGraph …
│       ├── stores/                # Pinia：medications、results
│       └── api/client.js          # fetch 封装（超时与错误统一处理）
│
└── deploy/
    ├── start_all.sh / start_all.bat   # 一键启动：initdb → uvicorn → vite
    ├── screenshots/                   # 预生成演示截图（断网兜底）
    └── docker-compose.yml             # 可选容器化
```

---

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/drugs/search?q=华法&limit=10` | 药名模糊搜索，返回候选与命中类型 |
| `POST` | `/api/check` | **核心接口**：药单两两 DDI 检查 |
| `GET` | `/api/graph?ids=DDInter1,DDInter1263` | 返回 `{nodes, links}`，直接喂给 ECharts |
| `GET` | `/api/report?medication_ids=...` | 报告聚合数据 |
| `POST` | `/api/lab/extract` | NLP 文献抽取演示 |

**`POST /api/check` 请求**

```json
{ "medications": ["华法林", "阿司匹林", "二甲双胍"] }
```

**响应**

```json
{
  "unresolved": [],
  "pairs": [
    {
      "drug_a": "华法林 (Warfarin)",
      "drug_b": "阿司匹林 (Aspirin)",
      "level": "Major",
      "mechanism_cn": "两药联用抗凝与抗血小板作用叠加，出血风险显著升高",
      "management": "避免联用，评估替代抗栓方案；如必须联用需密切监测",
      "mechanism_en": "The risk of bleeding is increased when Warfarin is combined with Aspirin.",
      "source_id": "DDInter1263"
    }
  ],
  "summary": { "Major": 1, "Moderate": 0, "Minor": 0, "overall": "red" },
  "coverage_note": "以下药物组合在数据库中无收录记录，不代表无相互作用"
}
```

启动后端后访问 `http://127.0.0.1:8000/docs` 查看完整交互式文档。

---

## 数据模型

```sql
-- 药品主表
CREATE TABLE drug (
  ddinter_id  TEXT PRIMARY KEY,      -- 'DDInter1263'
  name_en     TEXT NOT NULL,
  name_cn     TEXT,
  atc_code    TEXT, atc_name TEXT,
  drugbank_id TEXT, pubchem_id TEXT, chembl_id TEXT
);

-- DDI 关系表（无序对规范化：强制 ddinter_id_a < ddinter_id_b）
CREATE TABLE ddi (
  id           INTEGER PRIMARY KEY,
  ddinter_id_a TEXT NOT NULL REFERENCES drug(ddinter_id),
  ddinter_id_b TEXT NOT NULL REFERENCES drug(ddinter_id),
  level        TEXT NOT NULL CHECK (level IN ('Major','Moderate','Minor')),
  mechanism_id INTEGER REFERENCES mechanism(id),
  source_id    TEXT                 -- DDInter 记录 ID，用于页面溯源
);
CREATE UNIQUE INDEX idx_pair ON ddi(ddinter_id_a, ddinter_id_b);

-- 机制描述表（多条 DDI 可共享一条机制）
CREATE TABLE mechanism (
  id              INTEGER PRIMARY KEY,
  text_en         TEXT NOT NULL,
  text_cn_summary TEXT             -- 中文关键句摘要（LLM 辅助 + 人工抽检）
);

-- 别名映射表（中文匹配的关键，进 Git 版本化）
CREATE TABLE alias (
  alias       TEXT PRIMARY KEY,     -- '华法林' / 'warfarin' / 'hfl'
  kind        TEXT CHECK (kind IN ('cn','en','pinyin','synonym')),
  ddinter_id  TEXT NOT NULL REFERENCES drug(ddinter_id)
);
```

设计要点：**无序对规范化 + 复合唯一索引**是「两两检查 < 5 ms」的前提；机制文本独立成表避免重复存储；`alias` 表数据量小（千级）但价值极高，纳入 Git 并走 PR 审阅式维护。

---

## 核心检查算法

```
输入: 药单 M = [m1, ..., mn]（用户输入的原始药名）
输出: 风险列表 R + 整体分级

1. 归一化: 对每个 m_i 查 alias 表 → ddinter_id
           命中多个 → 精确匹配优先；零命中 → 加入 unresolved 并给出候选
           （候选 = 编辑距离 + 拼音前缀匹配，供用户确认）
2. 组合:   生成无序对集合 P = {(a,b) | a,b ∈ M, a < b}
3. 查询:   对每个 (a,b) 查 ddi 表（复合唯一索引命中）
4. 聚合:   同一对取最高风险等级（保守策略：宁可高报，不漏报）
5. 分级:   overall = Major>0 → 红；Moderate>0 → 橙；Minor>0 → 绿；
           全部无记录 → 灰，并提示「未收录 ≠ 无相互作用」
```

- **复杂度**：C(n,2) 次索引查询。n = 10 时 45 次，SQLite 实测 < 5 ms；前端限制单张药单 ≤ 20 种药。
- **诚实边界**：查无记录 ≠ 安全。对不在库内的药、以及库内无记录的组合，界面必须显式展示数据覆盖范围提示。这是审编库方法论的边界，也是本项目在医疗场景中的基本态度。

---

## 数据来源与许可

| 数据集 | 规模 | 许可 | 用途 |
|---|---|---|---|
| **DDInter 2.0**（[ddinter2.scbdd.com](https://ddinter2.scbdd.com)，Nucleic Acids Res 2025） | 官方口径：2,310 药、302,516 条 DDI、8,598 条机制描述；另含 857 DFI、8,359 DDSI、6,033 重复用药记录。**本项目实际入库：1,971 药 / 234,981 个唯一药对 / 21 条人工审编机制** | **CC BY-NC-SA 4.0** | 核心检查数据库（当前仅接入 DDI） |
| **DDIExtraction 2013** | 药品说明书文本标注的 DDI 关系，约 784 篇训练文档 | 公开（学术） | NLP 关系抽取训练/评测 |
| **DDIMDL** | 572 药、37,264 条 DDI、65 种事件类型 | 公开 | 事件预测实验基准 |
| **TwoSIDES** | 645 药、约 465 万药物对-副作用关联 | 研究用途 | 可选扩展（不进入 MVP） |
| **CMeKG** | 疾病/症状/药品中文术语 | 学术 | 中文别名与术语对齐 |

**合规要求（已落实到「关于」页与页脚）**

1. DDInter 为 **CC BY-NC-SA 4.0**：允许学术使用，但须**署名来源**、**禁止商用**、衍生数据须以相同方式共享。页面页脚标注「数据来源：DDInter 2.0 (CC BY-NC-SA 4.0)」。
2. TwoSIDES 源自 FAERS 自发报告，存在报告偏倚，仅作扩展参考。
3. 系统页面全程展示免责声明，见 [免责声明](#免责声明)。

---

## AI 能力：三层递进

> 故事线：**查得准（人工审编库）→ 抽得出（NLP 自动化）→ 推得到（预测模型）**，覆盖「知识 + 感知 + 预测」三个层面。

**层次 A · 检索式检查（主线，确定性输出）**
SQL 精确查询 DDInter 关系表，配合别名映射做药名归一化。中文对齐策略：自建「中文通用名 ↔ 英文通用名」映射表（已覆盖 **366 种常见药**，拼音首字母由 `pypinyin` 自动生成）；分子层面可利用 DDInter 自带的 DrugBank / PubChem / ChEMBL ID 去歧义。响应实测：10 药 45 组合 2.47 ms，20 药 190 组合 8.97 ms。

**层次 B · NLP 关系抽取（辅助，展示「AI 扩库」）**
输入一段说明书或文献文本，抽取三元组（药物 A，药物 B，相互作用类型）。模型二选一：PaddleNLP **UIE**（零样本、CPU 实时推理，成本最低）或 **BioBERT** 在 DDIExtraction 2013 上微调（有明确文献 F1 基准）。网站呈现为「AI 文献抽取实验室」：高亮实体 → 输出抽取三元组 → 一键与主库比对（新增 / 已存在）。

**层次 C · DDI 事件预测（选做，论文素材）**
DDIMDL 基准：572 药、65 种事件类型的多标签预测。方法为 RDKit Morgan 分子指纹 + 多标签分类（Logistic 基线 → MLP），产出 macro-F1 与原论文基线对比表。

---

## 测试与评估

| 维度 | 方法 |
|---|---|
| **单元测试** | `checker.py` 用 7 个经典案例 + 3 个安全对照断言风险等级；`alias.py` 断言大小写、别名、拼音首字母、未命中候选四条路径 |
| **接口测试** | FastAPI TestClient 覆盖正常流、未命中药名、空药单、n=1、n>20 边界 |
| **前端关键路径** | 载入模板 → 检查 → 展开卡片 → 导出报告，清单写入 `docs/demo_script.md` |
| **性能** | n=20 药单（190 组合）响应时间记录归档 |
| **数据画像** | 风险等级分布、ATC 分类分布、药品种类覆盖统计 |
| **检索准确性** | 100 条测试药单与 DDInter 官方在线工具人工比对，报告查全率 / 查准率 |
| **NLP 评测** | DDIExtraction 2013 测试集 P/R/F1（BioBERT 微调 vs UIE 零样本 vs 规则基线） |

```bash
make test                      # 全量测试
pytest backend/tests -k checker -v
```

---

## 路线图

| 阶段 | 目标 | 验收标志 | 状态 |
|---|---|---|---|
| **W0** | 仓库初始化、README、许可与目录约定 | 仓库可克隆、方案可读 | ✅ 完成 |
| **W1** | 数据管道：下载 → 清洗入库 → 别名表 v1 → FastAPI | `/api/check` 返回真实数据 | ✅ 完成（1971 药 / 234,981 对入库，31 测试通过） |
| **W2** | 前端骨架 + 药单页 + 检查结果页 | 3 组演示药单全流程可跑 | ✅ 完成（六页全成型，前后端联调打通） |
| **W3** | 图谱页 + DDSI/DFI/重复用药 + 报告导出 | 五个页面全部成型 | 🟡 图谱页 / 报告导出已完成；**DDSI / DFI / 重复用药未实现**（官方仅开放 DDI 的 CSV 下载，需另选数据源） |
| **W4** | NLP 模块（UIE 优先）+ 预测实验（选做） | 实验室页可演示 | 🟡 词典+模式规则基线可演示；**UIE/BioBERT 微调与事件预测未开始**（`ml/` 待建立） |
| **W5** | 测试 + 视觉打磨 + 部署 + 文档 | 交付物齐全 | 🟡 31 用例、单服务部署、[docs/](saferx/docs/) 五份文档与兜底截图已完成；**课程报告正文与正式上线未完成** |

**交付物索引**：[数据字典](saferx/docs/data_dictionary.md) · [接口文档](saferx/docs/api.md) · [演示脚本](saferx/docs/demo_script.md) · [数据画像](saferx/docs/data_profile.md) · [页面截图](saferx/deploy/screenshots/)

**分支与提交规范**：`main` 始终可运行；功能开发在 `feature/w1-data-pipeline` 式分支完成。提交信息遵循 Conventional Commits（`feat:` `fix:` `docs:` `data:`），里程碑打 tag（`w1-done` … `w5-submit`）。`data/external/alias.csv` 等入库数据的修改单独提交，message 注明修改依据。

---

## 经典演示案例

| 药物组合 | 风险级 | 机制要点 |
|---|---|---|
| 华法林 + 阿司匹林 | Major | 抗凝 + 抗血小板叠加，出血风险显著升高 |
| 华法林 + 胺碘酮 | Major | CYP2C9 抑制，INR 升高，需减量监测 |
| 辛伐他汀 + 克拉霉素 | Major | CYP3A4 强抑制，横纹肌溶解风险 |
| 左氧氟沙星 + 胺碘酮 | Major | QT 间期延长叠加，尖端扭转型室速风险 |
| 锂盐 + 氢氯噻嗪 | Major | 锂清除率下降，锂中毒 |
| 氯吡格雷 + 奥美拉唑 | Moderate | CYP2C19 抑制，抗血小板效应降低 |
| 帕罗西汀 + 曲马多 | Moderate | 5-羟色胺综合征风险 |

内置慢病模板药单（演示与测试共用）：

| 模板 | 药单 | 预期效果 |
|---|---|---|
| 高血压 + 房颤（主演示） | 华法林、胺碘酮、地高辛、氨氯地平、氢氯噻嗪 | 两条 Major 红卡 |
| 他汀 + 抗感染 | 辛伐他汀、克拉霉素、氨氯地平 | 横纹肌溶解，机制最清晰 |
| 抑郁 + 疼痛 | 帕罗西汀、曲马多、布洛芬 | Moderate 的处置逻辑 |
| 慢病日常（安全对照） | 氨氯地平、二甲双胍、阿托伐他汀 | 绿色界面，说明「大多数日常联用是安全的」 |

---

## 设计原则

1. **判断层用审编库，不用大模型。** LLM 幻觉不可控、证据不可溯；在用药安全这种场景里，可追溯性优先于覆盖面。LLM 只承担低风险任务（机制文本翻译与摘要），且经人工抽检。
2. **保守聚合。** 同一药物对命中多条记录时取最高风险等级；Minor 也照常展示，不隐藏、不降噪。
3. **未收录必须说清楚。** 查不到不等于安全，界面显式标注数据覆盖范围。
4. **零隐私负担。** 无账号体系、无埋点，药单仅在内存中处理、不落库，可完全离线运行。
5. **业务逻辑只写在 `services/`。** `checker` 为纯函数，可单测、可演示、可替换。

---

## 免责声明

> 本系统是面向教学与科普的用药信息参考工具，**不是诊断或处方工具**。检查结果基于公开审编数据库，可能不完整或滞后；实际用药请咨询医师或药师。本系统不收集任何个人健康数据。

---

## 参考文献

1. Xiong G, et al. **DDInter 2.0**: an enhanced drug interaction resource with expanded data coverage, new interaction types, and improved user interface. *Nucleic Acids Research*, 2025, 53(D1): D1356–D1362.
2. Tatonetti NP, et al. Data-driven prediction of drug effects and interactions. *Science Translational Medicine*, 2012, 4(125): 125ra31.
3. Deng Y, et al. A multimodal deep learning framework for predicting drug–drug interaction events. *Bioinformatics*, 2020, 36(14): 4316–4322.
4. Segura-Bedmar I, et al. The 1st DDIExtraction-2013 challenge task: extraction of drug–drug interactions from biomedical texts. *DMIR Workshop*, 2013.

---

## License

- **代码**：GNU General Public License v3.0，见 [LICENSE](LICENSE)。
- **数据**：本项目使用的 DDInter 2.0 数据集遵循 **CC BY-NC-SA 4.0**——署名、非商业、相同方式共享。本项目仅用于教学与科研，不得用于商业目的。

<div align="center">
<sub>合理用药，减少可预防的伤害。</sub>
</div>

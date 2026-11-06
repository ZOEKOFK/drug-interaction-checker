<script setup>
import { computed, onMounted, ref } from 'vue'
import { getStats } from '../api/client.js'

/* 规模数字一律读后端 meta，不在前端硬编码官方口径 */
const stats = ref(null)
onMounted(async () => {
  stats.value = await getStats()
})
const fmt = (n) => (n ?? 0).toLocaleString()
const pct = (a, b) => (b ? `${((a / b) * 100).toFixed(1)}%` : '—')

const OFFICIAL_DRUGS = 2310

const dataSources = computed(() => [
  {
    name: 'DDInter 2.0',
    scale: `官方 ${fmt(OFFICIAL_DRUGS)} 种药物 / ${fmt(302516)} 条 DDI；本项目实际入库 ${fmt(stats.value?.drugs)} 种药物 / ${fmt(stats.value?.ddi_pairs)} 个唯一药对`,
    license: 'CC BY-NC-SA 4.0',
    usage: `核心检查数据库 —— DDI 关系来自官方 CSV；DDSI / DFI / 重复用药官方未提供 CSV，经网页表格接口抓取，已入库 ${fmt(stats.value?.ddsi_rows)} / ${fmt(stats.value?.dfi_rows)} / ${fmt(stats.value?.dupli_rows)} 条`
  },
  {
    name: 'DDIExtraction 2013 Corpus',
    scale: '784 篇 DrugBank 说明书 + 175 篇 MEDLINE 摘要（Train 4,021 / Test 979 条关系）',
    license: 'CC BY-NC 4.0',
    usage: 'NLP 关系抽取评测 —— 已完成规则基线与 TF-IDF+LR 两档（见 docs/eval_nlp.md）；BioBERT 微调因无 GPU 未执行'
  },
  {
    name: 'DDIMDL',
    scale: '572 种药物 · 37,264 条 DDI · 65 种事件类型',
    license: '公开',
    usage: 'DDI 事件预测实验基准（选做，未开始）'
  }
])

const coverage = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    { k: '药物覆盖', v: `${fmt(s.drugs)} / ${fmt(OFFICIAL_DRUGS)}`, note: `官方库的 ${pct(s.drugs, OFFICIAL_DRUGS)}` },
    { k: '中文通用名覆盖', v: `${fmt(s.drugs_with_cn)} / ${fmt(s.drugs)}`, note: `可中文检索的药物占 ${pct(s.drugs_with_cn, s.drugs)}，其余需用英文名` },
    { k: '机制文本覆盖', v: `${fmt(s.mechanisms_covered_pairs)} / ${fmt(s.ddi_pairs)} 对`, note: '仅人工审编的经典案例有中文机制，其余显示「暂无」' },
    { k: '分级未知记录', v: `${fmt(s.levels?.Unknown)} 对`, note: `占全部药对 ${pct(s.levels?.Unknown, s.ddi_pairs)}，界面标注为「分级未知」而非「无风险」` },
    { k: '药物-疾病禁忌', v: `${fmt(s.ddsi_rows)} 条`, note: `覆盖 ${fmt(s.ddsi_diseases)} 种疾病，其中 ${fmt(s.ddsi_cn_covered)} 条已配中文疾病名` },
    { k: '药物-食物', v: `${fmt(s.dfi_rows)} 条`, note: `仅 ${fmt(s.dfi_foods)} 类食物（酒精、西柚汁等），覆盖范围窄，非全面食物禁忌` },
    { k: '治疗重复', v: `${fmt(s.dupli_rows)} 条`, note: `覆盖 ${fmt(s.dupli_categories)} 个治疗类别，同类别 ≥2 种即告警` }
  ]
})

const references = [
  'Xiong G, et al. DDInter 2.0: an enhanced drug interaction resource with expanded data coverage, new interaction types, and improved user interface. Nucleic Acids Research, 2025, 53(D1): D1356–D1362.',
  'Tatonetti NP, Ye PP, Daneshjou R, Altman RB. Data-driven prediction of drug effects and interactions. Science Translational Medicine, 2012, 4(125): 125ra31.',
  'Deng Y, et al. A multimodal deep learning framework for predicting drug–drug interaction events. Bioinformatics, 2020, 36(14): 4316–4322.',
  'Segura-Bedmar I, et al. The 1st DDIExtraction-2013 challenge task: extraction of drug–drug interactions from biomedical texts. DMIR Workshop, 2013.'
]

const stack = [
  { name: '前端', detail: 'Vue 3 · Vite · Tailwind CSS · Pinia · ECharts' },
  { name: '后端', detail: 'FastAPI · SQLite（无序对规范化 + 复合唯一索引）' },
  { name: '数据管道', detail: 'DDInter 2.0 CSV 清洗入库 · 网页表格接口抓取 DDSI/DFI/重复用药 · 中英别名映射（366 种中文名 + 拼音）' },
  { name: '模型层', detail: '当前为词典 + 规则基线（已在 DDIExtraction 2013 上评测）；BioBERT 微调受本机无 GPU 限制' }
]
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8 space-y-8">
    <!-- 页头 -->
    <div>
      <h1 class="text-2xl font-extrabold tracking-tight">关于 SafeRx</h1>
      <p class="mt-1.5 text-sm text-ink-soft max-w-3xl leading-relaxed">
        SafeRx（用药安全卫士）是「医疗人工智能」课程项目：面向大众与基层医护的用药安全检查工具。
        核心思路是——用人工审编的开放数据库做<b>检索式检查</b>保证可靠性，用 NLP 关系抽取做<b>自动扩库</b>展示 AI 价值，
        用<b>知识图谱可视化</b>降低理解门槛。
      </p>
    </div>

    <!-- 免责声明 -->
    <section class="card card-accent p-6">
      <h2 class="font-bold flex items-center gap-2">
        <svg class="w-5 h-5 text-risk-moderate" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke-linejoin="round" /><path d="M12 9v4M12 17h.01" stroke-linecap="round" />
        </svg>
        免责声明
      </h2>
      <p class="mt-3 text-sm text-ink-soft leading-relaxed">
        本系统是面向教学与科普的用药信息参考工具，<b>不是诊断或处方工具</b>。检查结果基于公开审编数据库，
        可能不完整或滞后；「未收录」不代表无相互作用。实际用药请咨询医师或药师。
        本系统不设用户账号、不收集任何个人健康数据，药单仅在内存中匿名处理。
      </p>
    </section>

    <!-- 数据来源与许可 -->
    <section>
      <h2 class="text-lg font-extrabold tracking-tight">数据来源与许可</h2>
      <div class="mt-4 card overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-primary-50 text-left text-xs text-ink-soft">
              <th class="px-4 py-3 font-bold">数据集</th>
              <th class="px-4 py-3 font-bold">规模</th>
              <th class="px-4 py-3 font-bold">许可</th>
              <th class="px-4 py-3 font-bold">用途</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in dataSources" :key="d.name" class="border-t border-line">
              <td class="px-4 py-3 font-semibold text-primary whitespace-nowrap">{{ d.name }}</td>
              <td class="px-4 py-3 text-ink-soft">{{ d.scale }}</td>
              <td class="px-4 py-3 text-ink-soft whitespace-nowrap">{{ d.license }}</td>
              <td class="px-4 py-3 text-ink-soft">{{ d.usage }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-2.5 text-xs text-ink-faint leading-relaxed">
        DDInter 2.0 采用 CC BY-NC-SA 4.0 许可：允许学术使用，须署名来源、禁止商用、衍生数据须相同方式共享。
        本项目为课程作业，符合上述条款，页脚已注明出处。
      </p>
    </section>

    <!-- 数据覆盖与已知局限 -->
    <section>
      <h2 class="text-lg font-extrabold tracking-tight">数据覆盖与已知局限</h2>
      <p class="mt-1.5 text-sm text-ink-soft leading-relaxed max-w-3xl">
        下列数字均由 <code class="text-xs bg-primary-50 text-primary px-1.5 py-0.5 rounded">/api/health</code>
        从数据库实时读出，不使用官方宣传口径。把边界写清楚，比把覆盖率说漂亮更重要。
      </p>
      <div class="mt-4 grid sm:grid-cols-2 gap-4">
        <div v-for="c in coverage" :key="c.k" class="card p-4">
          <div class="flex items-baseline justify-between gap-3">
            <p class="text-sm font-bold text-ink">{{ c.k }}</p>
            <p class="text-lg font-extrabold text-primary tabular-nums">{{ c.v }}</p>
          </div>
          <p class="mt-1.5 text-xs text-ink-faint leading-relaxed">{{ c.note }}</p>
        </div>
      </div>
      <ul class="mt-3 text-xs text-ink-soft space-y-1.5 list-disc pl-5 leading-relaxed">
        <li>DDInter 官方库含 2,310 种药物，本项目清洗后实际入库 1,971 种（差异来自跨分类重复与无效记录过滤）。</li>
        <li>英文名未收录的药（如部分国产仿制药商品名）无法检索——这是审编库的覆盖边界，不是「无风险」。</li>
        <li>拼音首字母存在 5 组天然冲突（如 klms 同时对应克拉霉素与克林霉素），冲突项不做映射，请改用中文全名。</li>
        <li>药物-食物数据仅 805 条 / 29 类食物（酒精占一半以上），只覆盖「酒精、西柚汁、高脂、高钾、维生素 K」等常见项，不能据此认为其他食物安全。</li>
        <li>药物-疾病禁忌的疾病中文名覆盖 150 / 459 种（按条目计约 89%），未覆盖者显示英文病名。</li>
        <li>查不到记录 ≠ 安全：界面与导出报告均固定展示该提示。</li>
      </ul>
    </section>

    <!-- 技术架构 -->
    <section>
      <h2 class="text-lg font-extrabold tracking-tight">技术架构</h2>
      <div class="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="s in stack" :key="s.name" class="card p-4">
          <p class="text-xs font-bold text-primary mb-1.5">{{ s.name }}</p>
          <p class="text-sm text-ink-soft leading-relaxed">{{ s.detail }}</p>
        </div>
      </div>
      <p class="mt-2.5 text-xs text-ink-faint leading-relaxed">
        前端仅经 /api 与后端通信；业务逻辑收敛于 services 层（核心 checker 为纯函数）；模型产物经固定接口交付后端，训练与推理隔离。
      </p>
    </section>

    <!-- 隐私 -->
    <section class="card p-6">
      <h2 class="font-bold flex items-center gap-2">
        <svg class="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 13c0 5-3.5 7.5-7.7 9a.6.6 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1Z" stroke-linejoin="round" />
        </svg>
        隐私承诺
      </h2>
      <ul class="mt-3 text-sm text-ink-soft space-y-1.5 list-disc pl-5 leading-relaxed">
        <li>无账号体系、无埋点、无第三方统计</li>
        <li>药单仅在浏览器内存中处理，刷新即清除，不落库</li>
        <li>可完全离线运行（SQLite 全本地 + 模型离线加载）</li>
        <li>导出报告默认匿名，不含任何个人信息</li>
      </ul>
    </section>

    <!-- 参考文献 -->
    <section>
      <h2 class="text-lg font-extrabold tracking-tight">参考文献</h2>
      <ol class="mt-3 space-y-2 text-sm text-ink-soft leading-relaxed list-decimal pl-5">
        <li v-for="(r, i) in references" :key="i">{{ r }}</li>
      </ol>
    </section>
  </div>
</template>

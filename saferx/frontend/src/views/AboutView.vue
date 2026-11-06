<script setup>
const dataSources = [
  {
    name: 'DDInter 2.0',
    scale: '2,310 种药物 · 302,516 条 DDI · 8,598 条机制描述',
    license: 'CC BY-NC-SA 4.0',
    usage: '核心检查数据库（含 DDI / DFI / DDSI / 重复用药）'
  },
  {
    name: 'DDIExtraction 2013 Corpus',
    scale: '约 784 篇 DrugBank 说明书标注文档',
    license: '公开（学术用途）',
    usage: 'NLP 关系抽取训练与评测'
  },
  {
    name: 'DDIMDL',
    scale: '572 种药物 · 37,264 条 DDI · 65 种事件类型',
    license: '公开',
    usage: 'DDI 事件预测实验基准'
  }
]

const references = [
  'Xiong G, et al. DDInter 2.0: an enhanced drug interaction resource with expanded data coverage, new interaction types, and improved user interface. Nucleic Acids Research, 2025, 53(D1): D1356–D1362.',
  'Tatonetti NP, Ye PP, Daneshjou R, Altman RB. Data-driven prediction of drug effects and interactions. Science Translational Medicine, 2012, 4(125): 125ra31.',
  'Deng Y, et al. A multimodal deep learning framework for predicting drug–drug interaction events. Bioinformatics, 2020, 36(14): 4316–4322.',
  'Segura-Bedmar I, et al. The 1st DDIExtraction-2013 challenge task: extraction of drug–drug interactions from biomedical texts. DMIR Workshop, 2013.'
]

const stack = [
  { name: '前端', detail: 'Vue 3 · Vite · Tailwind CSS · Pinia · ECharts' },
  { name: '后端', detail: 'FastAPI · SQLite（无序对规范化 + 复合唯一索引）' },
  { name: '数据管道', detail: 'DDInter 2.0 CSV 清洗入库 · 中英别名映射表' },
  { name: '模型层', detail: 'PaddleNLP UIE / BioBERT 关系抽取 · 分子指纹事件预测' }
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
    <section class="card p-6 border-l-4 border-l-risk-moderate">
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

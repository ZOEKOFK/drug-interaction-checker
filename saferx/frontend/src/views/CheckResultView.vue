<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMedStore } from '../stores/medications.js'
import { useResultStore } from '../stores/results.js'
import RiskCard from '../components/RiskCard.vue'
import RiskDonut from '../components/RiskDonut.vue'
import OtherRiskCard from '../components/OtherRiskCard.vue'

const router = useRouter()
const medStore = useMedStore()
const resultStore = useResultStore()

const report = computed(() => resultStore.report)

const filters = [
  { key: 'all', label: '全部' },
  { key: 'Major', label: '严重' },
  { key: 'Moderate', label: '中度' },
  { key: 'Minor', label: '轻微' },
  { key: 'Unknown', label: '未知' },
  { key: 'unrecorded', label: '未收录' }
]
const filterCounts = computed(() => ({
  all: resultStore.pairs.length,
  Major: resultStore.pairs.filter((p) => p.level === 'Major').length,
  Moderate: resultStore.pairs.filter((p) => p.level === 'Moderate').length,
  Minor: resultStore.pairs.filter((p) => p.level === 'Minor').length,
  Unknown: resultStore.pairs.filter((p) => p.level === 'Unknown').length,
  unrecorded: resultStore.unrecorded.length
}))

const OVERALL_META = {
  red: { label: '发现严重风险', cls: 'bg-risk-major text-white' },
  orange: { label: '发现中度风险', cls: 'bg-risk-moderate text-white' },
  green: { label: '仅轻微风险', cls: 'bg-risk-minor text-white' },
  gray: { label: '未发现收录风险', cls: 'bg-primary text-white' }
}
const overall = computed(() => {
  const meta = OVERALL_META[resultStore.summary.overall] || OVERALL_META.gray
  if (resultStore.summary.overall === 'gray' && resultStore.summary.Unknown > 0) {
    return { ...meta, label: '仅分级未知记录' }
  }
  return meta
})

/* ---------- 其他相互作用（DDSI / DFI / 重复用药） ---------- */
const diseaseRisks = computed(() => resultStore.diseaseRisks)
const foodRisks = computed(() => resultStore.foodRisks)
const duplications = computed(() => resultStore.duplications)
const diseaseCount = computed(
  () => resultStore.otherSummary.disease.Major + resultStore.otherSummary.disease.Moderate + resultStore.otherSummary.disease.Minor
)
const foodCount = computed(
  () => resultStore.otherSummary.food.Major + resultStore.otherSummary.food.Moderate + resultStore.otherSummary.food.Minor
)
const otherTotal = computed(() => diseaseCount.value + foodCount.value + duplications.value.length)
const otherMajor = computed(
  () => resultStore.otherSummary.disease.Major + resultStore.otherSummary.food.Major
)

/** 综合评级：DDI 与「其他相互作用」取更高者 */
const combinedOverall = computed(() => {
  const key = report.value?.overall_all || resultStore.summary.overall
  const meta = OVERALL_META[key] || OVERALL_META.gray
  const ddiKey = resultStore.summary.overall
  return {
    ...meta,
    escalated: key !== ddiKey && key === 'red'
  }
})

function levelTag(level) {
  return { Major: 'badge-major', Moderate: 'badge-moderate', Minor: 'badge-minor' }[level] || ''
}

/* ---------- 导出匿名报告（独立 HTML） ---------- */
function exportReport() {
  const r = report.value
  if (!r) return
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
  const time = new Date().toLocaleString('zh-CN')
  const LEVEL_CN = { Major: '严重', Moderate: '中度', Minor: '轻微', Unknown: '分级未知' }
  const diseaseCn = (en) => medStore.diseases.find((d) => d.name_en === en)?.name_cn || en

  const pairRow = (p) => `
    <tr>
      <td><span class="lv lv-${p.level.toLowerCase()}">${LEVEL_CN[p.level]}</span></td>
      <td><b>${esc(p.drug_a.name_cn)}</b>（${esc(p.drug_a.name_en)}）× <b>${esc(p.drug_b.name_cn)}</b>（${esc(p.drug_b.name_en)}）</td>
      <td>${esc(p.mechanism_cn || '官方未提供机制描述，可凭来源 ID 到 DDInter 官网查看。')}</td>
      <td>${esc(p.management)}</td>
    </tr>`

  // 其他相互作用（疾病禁忌 / 食物 / 重复用药）
  const diseaseRows = (r.disease_risks || []).map((x) => `
    <tr>
      <td><span class="lv lv-${x.level.toLowerCase()}">${LEVEL_CN[x.level]}</span></td>
      <td><b>${esc(x.drug.name_cn)}</b> × ${esc(x.disease_cn)}</td>
      <td>${esc(x.description_en || '')}</td>
    </tr>`).join('')

  const foodRows = (r.food_risks || []).map((x) => `
    <tr>
      <td><span class="lv lv-${x.level.toLowerCase()}">${LEVEL_CN[x.level]}</span></td>
      <td><b>${esc(x.drug.name_cn)}</b> × ${esc(x.food_cn)}</td>
      <td>${esc(x.mechanism_cn || '')}${x.management_en ? '<br>' + esc(x.management_en) : ''}</td>
    </tr>`).join('')

  const dupliBlock = (r.duplications || []).length
    ? `<h2 style="font-size:15px;margin-top:24px">治疗重复（${r.duplications.length} 组）</h2>
       ${r.duplications.map((g) => `<p style="font-size:13px"><b>${esc(g.category_cn)}</b>：${g.drugs.map((d) => esc(d.name_cn)).join('、')}</p>`).join('')}`
    : ''

  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>SafeRx 用药安全报告</title>
<style>
body{font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#1F2A26;background:#F6FAF8;margin:0;padding:40px 16px}
.page{max-width:820px;margin:0 auto;background:#fff;border:1px solid #DCE9E4;border-radius:12px;padding:36px}
h1{font-size:22px;margin:0 0 4px} .meta{color:#55655E;font-size:13px;margin-bottom:24px}
.summary{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.stat{flex:1;min-width:120px;border:1px solid #DCE9E4;border-radius:10px;padding:12px 16px}
.stat b{font-size:24px} .stat span{display:block;font-size:12px;color:#55655E;margin-top:2px}
.m{color:#A32D2D} .mo{color:#854F0B} .mi{color:#3B6D11} .mu{color:#55655E}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#F0F8F5;text-align:left;padding:8px 10px;border-bottom:2px solid #DCE9E4}
td{padding:10px;border-bottom:1px solid #DCE9E4;vertical-align:top}
.lv{display:inline-block;border-radius:99px;padding:1px 10px;font-size:12px;font-weight:600}
.lv-major{background:#F8E9E9;color:#A32D2D} .lv-moderate{background:#F9EFE0;color:#854F0B} .lv-minor{background:#EAF2E1;color:#3B6D11} .lv-unknown{background:#EDF2F0;color:#55655E}
.disc{margin-top:28px;background:#F0F8F5;border-left:4px solid #0F6E56;padding:14px 16px;font-size:12px;color:#55655E;line-height:1.7}
</style></head><body><div class="page">
<h1>SafeRx 用药安全检查报告</h1>
<p class="meta">生成时间：${time} · 数据版本：${esc(r.data_version)} · 匿名报告（不含任何个人信息）</p>
<div class="summary">
<div class="stat"><b class="m">${r.summary.Major}</b><span>严重 Major</span></div>
<div class="stat"><b class="mo">${r.summary.Moderate}</b><span>中度 Moderate</span></div>
<div class="stat"><b class="mi">${r.summary.Minor}</b><span>轻微 Minor</span></div>
<div class="stat"><b class="mu">${r.summary.Unknown ?? 0}</b><span>分级未知 Unknown</span></div>
<div class="stat"><b>${(r.disease_risks?.length || 0) + (r.food_risks?.length || 0) + (r.duplications?.length || 0)}</b><span>其他相互作用</span></div>
<div class="stat"><b>${medStore.count}</b><span>药单药物数</span></div>
</div>
<h2 style="font-size:15px">药单（${medStore.count} 种）</h2>
<p style="font-size:13px">${medStore.drugs.map((d) => esc(`${d.name_cn}（${d.name_en}）`)).join('、')}</p>
${(r.diseases_checked || []).length ? `<p style="font-size:13px;color:#55655E">基础疾病：${r.diseases_checked.map((d) => esc(diseaseCn(d))).join('、')}</p>` : '<p style="font-size:13px;color:#55655E">未提供基础疾病，未执行疾病禁忌检查。</p>'}
<h2 style="font-size:15px;margin-top:24px">收录的相互作用（${r.pairs.length} 条）</h2>
${r.pairs.length ? `<table><tr><th>级别</th><th>药物组合</th><th>机制摘要</th><th>处置建议</th></tr>${r.pairs.map(pairRow).join('')}</table>` : '<p style="font-size:13px">当前药单在数据库中未收录任何相互作用记录。</p>'}
${r.unrecorded_pairs.length ? `<h2 style="font-size:15px;margin-top:24px">未收录组合（${r.unrecorded_pairs.length} 对）</h2>
<p style="font-size:13px">${r.unrecorded_pairs.map((p) => esc(`${p.drug_a.name_cn} × ${p.drug_b.name_cn}`)).join('、')}</p>` : ''}
${(r.disease_risks || []).length ? `<h2 style="font-size:15px;margin-top:24px">药物 × 基础疾病禁忌（${r.disease_risks.length} 条）</h2>
<table><tr><th>级别</th><th>药物 × 疾病</th><th>说明（DDInter 原文）</th></tr>${diseaseRows}</table>` : ''}
${(r.food_risks || []).length ? `<h2 style="font-size:15px;margin-top:24px">药物 × 食物 / 烟酒（${r.food_risks.length} 条）</h2>
<table><tr><th>级别</th><th>药物 × 食物</th><th>机制与处置</th></tr>${foodRows}</table>` : ''}
${dupliBlock}
<div class="disc"><b>免责声明：</b>本报告由 SafeRx 生成，仅供教学与科普参考，<b>不构成诊断或处方依据</b>。检查结果基于 DDInter 2.0 审编数据库（CC BY-NC-SA 4.0），可能不完整或滞后；「未收录」不代表无相互作用。实际用药请咨询医师或药师。</div>
</div></body></html>`

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `SafeRx-用药安全报告-${new Date().toISOString().slice(0, 10)}.html`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <!-- 无结果时引导 -->
    <div v-if="!report" class="card p-10 text-center">
      <p class="text-ink-soft font-medium">还没有检查结果</p>
      <p class="text-ink-faint text-sm mt-1">请先在药单页添加药物并运行检查</p>
      <div class="mt-5 flex justify-center gap-3">
        <button class="btn-primary" @click="router.push('/medications')">前往我的药单</button>
        <button class="btn-ghost" @click="router.push('/')">回到首页</button>
      </div>
    </div>

    <template v-else>
      <!-- ============ 汇总头 ============ -->
      <div class="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div class="flex items-center gap-3 flex-wrap">
            <h1 class="text-2xl font-extrabold tracking-tight">检查结果</h1>
            <span class="badge badge-dot" :class="combinedOverall.cls">{{ combinedOverall.label }}</span>
            <span v-if="combinedOverall.escalated" class="badge badge-major">含其他相互作用升级</span>
          </div>
          <p class="mt-1 text-sm text-ink-soft">
            {{ medStore.count }} 种药物 · {{ medStore.pairCount }} 个组合完成比对 · {{ report.data_version }}
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn-ghost no-print" @click="router.push('/graph')">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="6" cy="6" r="3" /><circle cx="18" cy="6" r="3" /><circle cx="12" cy="18" r="3" />
              <path d="M8.7 7.7 10.5 15.6M15.3 7.7 13.5 15.6M9 6h6" />
            </svg>
            查看交互图谱
          </button>
          <button class="btn-primary no-print" @click="exportReport">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            导出安全报告
          </button>
        </div>
      </div>

      <!-- 汇总卡 -->
      <div class="mt-5 card p-5 grid md:grid-cols-[190px_1fr] gap-6 items-center">
        <RiskDonut
          :major="resultStore.summary.Major"
          :moderate="resultStore.summary.Moderate"
          :minor="resultStore.summary.Minor"
          :unknown="resultStore.summary.Unknown"
          :size="185"
        />
        <div>
          <!-- 未命中药名提示 -->
          <div v-if="report.unresolved.length" class="mb-4 rounded-xl bg-risk-moderate-bg p-3.5">
            <p class="text-sm font-bold text-risk-moderate">有 {{ report.unresolved.length }} 个药名未能识别</p>
            <p class="mt-1 text-xs text-ink-soft leading-relaxed">
              <template v-for="(u, i) in report.unresolved" :key="i">
                「{{ u.input }}」<template v-if="u.candidates.length">，可能是：{{ u.candidates.map((c) => c.name_cn).join('、') }}</template><template v-else>（未找到相近候选）</template>；
              </template>
              请修改药名后在药单页重新检查。
            </p>
          </div>

          <!-- 筛选器 -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="f in filters"
              :key="f.key"
              class="px-4 py-1.5 rounded-full text-sm font-semibold border transition-colors"
              :class="resultStore.filter === f.key
                ? 'bg-primary text-white border-primary'
                : 'bg-white text-ink-soft border-line hover:border-primary-bright hover:text-primary'"
              @click="resultStore.filter = f.key"
            >
              {{ f.label }}
              <span class="ml-1 tabular-nums opacity-80">{{ filterCounts[f.key] }}</span>
            </button>
          </div>

          <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="rounded-xl bg-risk-major-bg p-3 text-center">
              <p class="text-2xl font-extrabold text-risk-major tabular-nums">{{ resultStore.summary.Major }}</p>
              <p class="text-xs text-risk-major/80 mt-0.5">严重 · 避免联用</p>
            </div>
            <div class="rounded-xl bg-risk-moderate-bg p-3 text-center">
              <p class="text-2xl font-extrabold text-risk-moderate tabular-nums">{{ resultStore.summary.Moderate }}</p>
              <p class="text-xs text-risk-moderate/80 mt-0.5">中度 · 监测/调量</p>
            </div>
            <div class="rounded-xl bg-risk-minor-bg p-3 text-center">
              <p class="text-2xl font-extrabold text-risk-minor tabular-nums">{{ resultStore.summary.Minor }}</p>
              <p class="text-xs text-risk-minor/80 mt-0.5">轻微 · 一般可联用</p>
            </div>
            <div class="rounded-xl bg-[#EDF2F0] p-3 text-center">
              <p class="text-2xl font-extrabold text-ink-soft tabular-nums">{{ resultStore.summary.Unknown }}</p>
              <p class="text-xs text-ink-soft/80 mt-0.5">分级未知 · 谨慎</p>
            </div>
          </div>

          <p class="mt-3 text-xs text-ink-faint leading-relaxed">
            聚合策略：同一组合取最高风险等级（宁可高报不漏报）· 逐条输出证据来源可溯源 · 「分级未知」为 DDInter 官方未标注严重度的记录
          </p>
        </div>
      </div>

      <!-- ============ 风险卡片列表 ============ -->
      <section v-if="resultStore.filter !== 'unrecorded'" class="mt-6 space-y-4">
        <h2 class="text-sm font-bold text-ink-soft">
          收录的相互作用
          <span class="text-ink-faint font-normal">（按严重度降序，点击展开机制与处置）</span>
        </h2>
        <template v-if="resultStore.filteredPairs.length">
          <RiskCard v-for="(p, i) in resultStore.filteredPairs" :key="p.drug_a.ddinter_id + p.drug_b.ddinter_id + i" :pair="p" />
        </template>
        <div v-else class="card p-8 text-center text-ink-soft text-sm">当前筛选下暂无记录</div>
      </section>

      <!-- ============ 其他相互作用（疾病禁忌 / 食物 / 重复用药） ============ -->
      <section v-if="otherTotal" class="mt-8">
        <div class="flex items-center gap-2 flex-wrap">
          <h2 class="text-sm font-bold text-ink-soft">其他相互作用</h2>
          <span class="badge badge-clear">{{ otherTotal }} 项</span>
          <span v-if="otherMajor" class="badge badge-major">其中 {{ otherMajor }} 项严重</span>
        </div>

        <!-- 药物 × 疾病 -->
        <div v-if="diseaseRisks.length" class="mt-3">
          <h3 class="text-xs font-bold text-ink-faint tracking-wide mb-2">
            药物 × 基础疾病（DDSI）· {{ diseaseRisks.length }} 条
          </h3>
          <div class="space-y-2.5">
            <OtherRiskCard v-for="(r, i) in diseaseRisks" :key="'d' + i" :item="r" kind="disease" />
          </div>
        </div>

        <!-- 药物 × 食物 -->
        <div v-if="foodRisks.length" class="mt-5">
          <h3 class="text-xs font-bold text-ink-faint tracking-wide mb-2">
            药物 × 食物 / 烟酒（DFI）· {{ foodRisks.length }} 条
          </h3>
          <div class="space-y-2.5">
            <OtherRiskCard v-for="(r, i) in foodRisks" :key="'f' + i" :item="r" kind="food" />
          </div>
        </div>

        <!-- 治疗重复 -->
        <div v-if="duplications.length" class="mt-5">
          <h3 class="text-xs font-bold text-ink-faint tracking-wide mb-2">
            治疗重复 · {{ duplications.length }} 组
          </h3>
          <div class="space-y-2.5">
            <div
              v-for="(g, i) in duplications"
              :key="'g' + i"
              class="relative card p-4 pl-5 overflow-hidden"
            >
              <span class="absolute left-0 top-0 bottom-0 w-1 bg-risk-moderate" />
              <div class="flex items-center gap-2 flex-wrap">
                <h4 class="font-bold text-ink text-[14px]">{{ g.category_cn }}</h4>
                <span class="text-ink-faint text-[11px]">{{ g.category_en }}</span>
                <span class="badge badge-moderate">{{ g.drugs.length }} 种同类别</span>
              </div>
              <p class="mt-2 text-[13px] text-ink leading-relaxed">{{ g.summary_cn }}</p>
              <div class="mt-2 flex flex-wrap gap-1.5">
                <span
                  v-for="d in g.drugs"
                  :key="d.ddinter_id"
                  class="px-2.5 py-1 rounded-full bg-paper border border-line text-xs font-medium text-ink-soft"
                >
                  {{ d.name_cn }}
                </span>
              </div>
              <details v-if="g.warning_en" class="mt-2">
                <summary class="text-[11px] text-primary cursor-pointer select-none font-semibold">
                  展开原始警告（DDInter 英文原文）
                </summary>
                <p class="mt-1.5 text-[12px] text-ink-soft leading-relaxed">{{ g.warning_en }}</p>
              </details>
            </div>
          </div>
        </div>

        <p v-if="report.other_note" class="mt-3 text-xs text-ink-faint leading-relaxed">{{ report.other_note }}</p>
      </section>

      <div
        v-else-if="!report.diseases_checked?.length"
        class="mt-6 card p-4 border-dashed text-xs text-ink-faint leading-relaxed"
      >
        未提供基础疾病，已跳过药物-疾病禁忌检查；药单也未命中食物或治疗重复记录。如需检查疾病禁忌，请在药单页选择基础疾病后重新检查。
      </div>

      <!-- ============ 未收录组合（诚实边界） ============ -->
      <section v-if="resultStore.unrecorded.length && (resultStore.filter === 'all' || resultStore.filter === 'unrecorded')" class="mt-8">
        <div class="flex items-center gap-2">
          <h2 class="text-sm font-bold text-ink-soft">未收录组合</h2>
          <span class="badge badge-clear">{{ resultStore.unrecorded.length }} 对</span>
        </div>
        <div class="mt-3 card p-5 border-dashed">
          <div class="flex flex-wrap gap-2">
            <span
              v-for="(p, i) in resultStore.unrecorded"
              :key="i"
              class="px-3 py-1.5 rounded-full bg-paper border border-line text-xs text-ink-soft font-medium"
            >
              {{ p.drug_a.name_cn }} × {{ p.drug_b.name_cn }}
            </span>
          </div>
          <p class="mt-4 text-xs text-ink-faint leading-relaxed flex gap-1.5">
            <svg class="w-4 h-4 shrink-0 mt-px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" stroke-linecap="round" />
            </svg>
            {{ report.coverage_note }} 数据库收录 2,310 种已批准药物，「未收录」不代表无相互作用——这是审编数据库方法论的边界。
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

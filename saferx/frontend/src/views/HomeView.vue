<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMedStore } from '../stores/medications.js'
import { useResultStore } from '../stores/results.js'
import { check as apiCheck, getTemplates } from '../api/client.js'
import DrugSearchBox from '../components/DrugSearchBox.vue'
import PillChip from '../components/PillChip.vue'
import { useCountUp } from '../composables/useCountUp.js'

const router = useRouter()
const medStore = useMedStore()
const resultStore = useResultStore()

const statDrugs = useCountUp(2310)
const statDdi = useCountUp(302516)
const statMech = useCountUp(8598)

const templates = ref([])
onMounted(async () => {
  templates.value = await getTemplates()
})

function onSelect(drug) {
  medStore.add(drug)
  router.push('/medications')
}

async function loadTemplate(tpl) {
  medStore.loadTemplate(tpl.drugs)
  const result = await apiCheck(medStore.ids)
  resultStore.setPreview(result)
  router.push('/medications')
}

const steps = [
  {
    icon: 'M11 5a4 4 0 0 0-4 4c0 .5.1 1 .3 1.4-1.2.6-2 1.8-2 3.2a3.5 3.5 0 0 0 3.5 3.5h7a3.5 3.5 0 0 0 3.5-3.5c0-1.4-.8-2.6-2-3.2.2-.4.3-.9.3-1.4a4 4 0 0 0-4-4h-2z',
    title: '建立药单',
    desc: '输入药名或一键载入慢病模板，把你正在吃的药加进「药盒」。'
  },
  {
    icon: 'm21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z',
    title: '两两智能检查',
    desc: '系统对药单内所有 C(n,2) 组合逐一比对 30 万条审编 DDI 记录。'
  },
  {
    icon: 'M3 3v18h18M7 15l4-6 3 4 5-8',
    title: '读懂风险图谱',
    desc: '三级风险卡片 + 作用机制 + 处置建议 + 可交互知识图谱。'
  }
]
</script>

<template>
  <div>
    <!-- ============ Hero ============ -->
    <section class="dot-grid border-b border-line">
      <div class="max-w-6xl mx-auto px-4 pt-16 pb-12 text-center">
        <span class="badge badge-clear badge-dot mb-5 inline-flex">基于 DDInter 2.0 审编数据库 · 2310 种已批准药物</span>
        <h1 class="text-4xl sm:text-5xl font-extrabold tracking-tight text-ink leading-tight">
          一张药单，
          <span class="text-primary">看清所有</span>药物相互作用
        </h1>
        <p class="mt-4 text-ink-soft text-lg max-w-2xl mx-auto leading-relaxed">
          面向大众与基层医护的用药安全检查工具——输入药单，自动检出两两相互作用，
          给出风险分级、发生机制与处置建议，并以知识图谱直观呈现。
        </p>

        <!-- 大搜索框 -->
        <div class="mt-8 max-w-2xl mx-auto">
          <DrugSearchBox size="large" @select="onSelect" />
          <p class="mt-3 text-xs text-ink-faint">试试搜索：华法林 · 阿司匹林 · 克拉霉素 · hfl（拼音首字母）</p>
        </div>

        <!-- 心电监护线 -->
        <div class="mt-10 max-w-3xl mx-auto opacity-80" aria-hidden="true">
          <svg viewBox="0 0 720 60" class="w-full h-14" fill="none">
            <path
              class="ekg-line"
              d="M0 30h90l14-22 10 44 12-38 8 16h80l10-14 8 28 10-30 6 10h120l12-20 10 38 10-30 6 12h110l10-12 8 24 10-26 6 8h140"
              stroke="#0F6E56" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
            />
          </svg>
        </div>

        <!-- 数据规模 -->
        <div class="mt-8 max-w-3xl mx-auto card py-6 px-4 grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-line">
          <div class="py-2">
            <p class="text-3xl font-extrabold text-primary tabular-nums">{{ statDrugs.toLocaleString() }}</p>
            <p class="text-xs text-ink-faint mt-1">收录药物</p>
          </div>
          <div class="py-2">
            <p class="text-3xl font-extrabold text-primary tabular-nums">{{ statDdi.toLocaleString() }}</p>
            <p class="text-xs text-ink-faint mt-1">DDI 记录</p>
          </div>
          <div class="py-2 sm:border-t-0 border-t border-line">
            <p class="text-3xl font-extrabold text-primary tabular-nums">{{ statMech.toLocaleString() }}</p>
            <p class="text-xs text-ink-faint mt-1">机制描述</p>
          </div>
          <div class="py-2 sm:border-t-0 border-t border-line">
            <p class="text-3xl font-extrabold text-primary">&lt;5<span class="text-base font-bold">ms</span></p>
            <p class="text-xs text-ink-faint mt-1">10 种药全组合检查</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 三步使用 ============ -->
    <section class="max-w-6xl mx-auto px-4 py-12">
      <h2 class="text-2xl font-extrabold tracking-tight text-center">三步完成一次用药安全检查</h2>
      <div class="mt-8 grid sm:grid-cols-3 gap-5">
        <div v-for="(s, i) in steps" :key="i" class="card card-hover p-6 relative overflow-hidden">
          <span class="absolute -top-3 -right-2 text-[88px] font-extrabold text-primary-50 select-none leading-none">{{ i + 1 }}</span>
          <div class="relative">
            <div class="w-12 h-12 rounded-xl bg-primary-100 text-primary flex items-center justify-center mb-4">
              <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path :d="s.icon" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
            <h3 class="font-bold text-ink text-lg">{{ s.title }}</h3>
            <p class="mt-2 text-sm text-ink-soft leading-relaxed">{{ s.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 慢病模板药单 ============ -->
    <section class="bg-white border-y border-line">
      <div class="max-w-6xl mx-auto px-4 py-12">
        <div class="flex items-end justify-between flex-wrap gap-3">
          <div>
            <h2 class="text-2xl font-extrabold tracking-tight">慢病示例药单</h2>
            <p class="mt-1.5 text-ink-soft text-sm">一键载入典型慢病共病用药组合，体验完整检查流程</p>
          </div>
          <span class="text-xs text-ink-faint">演示模板 · 与后端 template 表同源</span>
        </div>

        <div class="mt-7 grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div
            v-for="tpl in templates"
            :key="tpl.id"
            class="card card-hover p-5 flex flex-col"
            :class="tpl.id === 'tpl-4' ? 'border-dashed' : ''"
          >
            <div class="flex items-center gap-2">
              <span class="w-9 h-9 rounded-lg bg-primary-100 text-primary flex items-center justify-center">
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4.8 2.3A.3.3 0 1 1 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 1 .3.3" /><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" /><circle cx="20" cy="10" r="2" />
                </svg>
              </span>
              <h3 class="font-bold text-ink">{{ tpl.name }}</h3>
            </div>
            <p class="mt-2.5 text-xs text-ink-soft leading-relaxed min-h-[2.4em]">{{ tpl.desc }}</p>
            <div class="mt-3 flex flex-wrap gap-1.5">
              <PillChip v-for="d in tpl.drugs" :key="d.ddinter_id" :drug="d" :removable="false" compact />
            </div>
            <button class="btn-primary mt-4 w-full text-sm" @click="loadTemplate(tpl)">载入药单并预检</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 底部引导 ============ -->
    <section class="max-w-6xl mx-auto px-4 py-12">
      <div class="card p-8 bg-primary text-white relative overflow-hidden">
        <div class="absolute -right-10 -top-10 w-48 h-48 rounded-full bg-white/10 float-soft" aria-hidden="true" />
        <div class="absolute -right-24 top-16 w-64 h-64 rounded-full bg-white/5" aria-hidden="true" />
        <div class="relative flex flex-wrap items-center justify-between gap-5">
          <div>
            <h2 class="text-2xl font-extrabold">已经准备好你的药单了？</h2>
            <p class="mt-2 text-white/85 text-sm">药单最多 20 种药物 · 检查在浏览器本地完成匿名比对，不留存任何数据</p>
          </div>
          <div class="flex gap-3">
            <button class="bg-white text-primary font-semibold rounded-full px-6 py-3 hover:bg-primary-50 transition-colors" @click="router.push('/medications')">
              前往我的药单
            </button>
            <router-link to="/lab" class="border border-white/50 text-white font-semibold rounded-full px-6 py-3 hover:bg-white/10 transition-colors">
              逛逛 AI 实验室
            </router-link>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMedStore } from '../stores/medications.js'
import { useResultStore } from '../stores/results.js'
import ForceGraph from '../components/ForceGraph.vue'

const router = useRouter()
const medStore = useMedStore()
const resultStore = useResultStore()

const graphData = ref({ nodes: [], links: [] })
const onlyMajor = ref(false)
const selectedNode = ref(null)
const loading = ref(false)

onMounted(async () => {
  if (medStore.count >= 2 && !resultStore.report) {
    await resultStore.runCheck(medStore.ids)
  }
  await loadGraph()
})

async function loadGraph() {
  if (medStore.count < 2) return
  loading.value = true
  try {
    graphData.value = await resultStore.loadGraph(medStore.ids)
  } finally {
    loading.value = false
  }
}

/** 选中节点的关联风险（来自完整检查结果） */
const nodeRisks = computed(() => {
  const n = selectedNode.value
  if (!n) return []
  return resultStore.pairs.filter(
    (p) => p.drug_a.ddinter_id === n.id || p.drug_b.ddinter_id === n.id
  )
})

const LEVEL_BADGE = { Major: 'badge-major', Moderate: 'badge-moderate', Minor: 'badge-minor', Unknown: 'badge-unknown' }
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <div class="flex items-start justify-between flex-wrap gap-4">
      <div>
        <h1 class="text-2xl font-extrabold tracking-tight">交互图谱</h1>
        <p class="mt-1 text-sm text-ink-soft">
          药单药物为节点，联用关系为边——边颜色即风险分级，节点描边指示其涉及的最高风险
        </p>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        <div class="flex items-center gap-3 text-xs font-semibold text-ink-soft bg-white border border-line rounded-full px-4 py-2">
          <span class="flex items-center gap-1.5"><i class="w-4 h-1 rounded inline-block bg-risk-major" />严重</span>
          <span class="flex items-center gap-1.5"><i class="w-4 h-1 rounded inline-block bg-risk-moderate" />中度</span>
          <span class="flex items-center gap-1.5"><i class="w-4 h-1 rounded inline-block bg-risk-minor" />轻微</span>
          <span class="flex items-center gap-1.5"><i class="w-4 h-1 rounded inline-block bg-ink-faint" />未知</span>
        </div>
        <button
          class="px-4 py-2 rounded-full text-sm font-semibold border transition-colors"
          :class="onlyMajor ? 'bg-risk-major text-white border-risk-major' : 'bg-white text-ink-soft border-line hover:border-risk-major hover:text-risk-major'"
          @click="onlyMajor = !onlyMajor"
        >
          只看严重风险
        </button>
        <button class="btn-ghost" @click="loadGraph">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          重新布局
        </button>
      </div>
    </div>

    <!-- 药单不足 -->
    <div v-if="medStore.count < 2" class="mt-6 card p-10 text-center">
      <p class="text-ink-soft font-medium">药单药物不足</p>
      <p class="text-ink-faint text-sm mt-1">图谱需要至少 2 种药物，请先完善药单</p>
      <button class="btn-primary mt-5" @click="router.push('/medications')">前往我的药单</button>
    </div>

    <div v-else class="mt-6 grid lg:grid-cols-[1fr_320px] gap-5 items-stretch">
      <!-- 图谱画布 -->
      <div class="card relative dot-grid overflow-hidden" style="min-height: 560px">
        <div v-if="loading" class="absolute inset-0 z-10 bg-white/70 flex items-center justify-center text-ink-soft text-sm font-semibold">
          正在构建关系子图…
        </div>
        <ForceGraph :nodes="graphData.nodes" :links="graphData.links" :only-major="onlyMajor" @node-click="selectedNode = $event" />
        <p class="absolute bottom-3 left-4 text-[11px] text-ink-faint no-select pointer-events-none">
          滚轮缩放 · 拖拽移动 · 拖动节点重新布局 · 点击节点查看详情
        </p>
      </div>

      <!-- 节点详情面板 -->
      <div class="card p-5 h-full flex flex-col">
        <h2 class="font-bold text-sm">节点详情</h2>
        <div v-if="!selectedNode" class="flex-1 flex items-center justify-center text-center py-10">
          <p class="text-ink-faint text-xs leading-relaxed">点击图谱中的节点<br />查看该药物信息与关联风险</p>
        </div>
        <template v-else>
          <div class="mt-3 p-4 rounded-xl bg-primary-50">
            <p class="font-extrabold text-lg text-ink">{{ selectedNode.name }}</p>
            <p class="text-xs text-ink-soft mt-0.5">{{ selectedNode.name_en }}</p>
            <div class="mt-2.5 flex flex-wrap gap-1.5">
              <span class="badge badge-clear">{{ selectedNode.category }}</span>
              <span class="badge badge-clear">关联 {{ selectedNode.degree }} 条</span>
            </div>
          </div>
          <div class="mt-4 flex-1 min-h-0 overflow-y-auto pr-1 space-y-2">
            <p v-if="!nodeRisks.length" class="text-xs text-ink-faint text-center py-6">该药物暂无收录的相互作用</p>
            <div v-for="(p, i) in nodeRisks" :key="i" class="p-3 rounded-lg border border-line bg-white">
              <div class="flex items-center justify-between gap-2">
                <p class="text-sm font-semibold text-ink">
                  {{ p.drug_a.name_cn === selectedNode.name ? p.drug_b.name_cn : p.drug_a.name_cn }}
                </p>
                <span class="badge badge-dot shrink-0" :class="LEVEL_BADGE[p.level]">{{ p.level_cn }}</span>
              </div>
              <p class="mt-1 text-xs text-ink-soft leading-relaxed line-clamp-2">{{ p.mechanism_cn }}</p>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

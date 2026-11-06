<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMedStore } from './stores/medications.js'
import { getStats } from './api/client.js'
import DisclaimerBar from './components/DisclaimerBar.vue'

const router = useRouter()
const medStore = useMedStore()

/* 后端离线时（断网答辩场景）给出明确标识，避免把演示子集误当全量数据 */
const offline = ref(false)
const offlineStats = ref(null)
onMounted(async () => {
  const s = await getStats()
  offline.value = !!s.offline
  offlineStats.value = s
})

const navItems = [
  { path: '/', label: '首页' },
  { path: '/medications', label: '我的药单' },
  { path: '/results', label: '检查结果' },
  { path: '/graph', label: '交互图谱' },
  { path: '/lab', label: 'AI 实验室' },
  { path: '/about', label: '关于' }
]

function goMedications() {
  router.push('/medications')
}
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- 顶部导航 -->
    <header class="no-print sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-line">
      <div class="max-w-6xl mx-auto px-4 h-16 flex items-center gap-6">
        <router-link to="/" class="flex items-center gap-2.5 shrink-0 group">
          <svg class="w-9 h-9 transition-transform group-hover:scale-105" viewBox="0 0 24 24">
            <path fill="#0F6E56" d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5z" />
            <path fill="white" d="M11 8h2v3h3v2h-3v3h-2v-3H8v-2h3z" />
          </svg>
          <span class="leading-tight">
            <span class="block font-extrabold text-[17px] text-ink tracking-tight">SafeRx</span>
            <span class="block text-[11px] text-ink-faint font-medium">用药安全卫士</span>
          </span>
        </router-link>

        <nav class="flex-1 flex items-center justify-center gap-1 min-w-0 overflow-x-auto">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="px-3.5 py-2 rounded-full text-sm font-semibold text-ink-soft hover:text-primary hover:bg-primary-50 transition-colors whitespace-nowrap"
            exact-active-class="!text-primary !bg-primary-100"
          >
            {{ item.label }}
          </router-link>
        </nav>

        <!-- 药单入口徽标 -->
        <span
          v-if="offline"
          class="shrink-0 hidden sm:inline-flex items-center gap-1.5 rounded-full bg-risk-moderate-bg text-risk-moderate px-3 py-1.5 text-xs font-bold"
          :title="`后端未连接，已降级为离线演示数据（${offlineStats?.drugs ?? 0} 种药 / ${offlineStats?.ddi_pairs ?? 0} 条关系）`"
        >
          <i class="w-1.5 h-1.5 rounded-full bg-risk-moderate inline-block" />
          离线演示数据
        </span>
        <button
          class="shrink-0 flex items-center gap-2 border border-primary-soft rounded-full pl-3 pr-4 py-1.5 text-sm font-semibold text-primary hover:bg-primary-50 transition-colors"
          title="查看我的药单"
          @click="goMedications"
        >
          <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="8" width="18" height="5" rx="2" /><path d="M12 8v5M7 8c0-1.7 1-3 2.5-3S12 6.3 12 8c0-1.7 1-3 2.5-3S17 6.3 17 8" /><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" />
          </svg>
          药单
          <span class="bg-primary text-white text-xs rounded-full min-w-5 h-5 px-1.5 inline-flex items-center justify-center font-bold">
            {{ medStore.count }}
          </span>
        </button>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="flex-1">
      <router-view v-slot="{ Component }">
        <Transition
          enter-active-class="transition duration-200 ease-out"
          enter-from-class="opacity-0 translate-y-1.5"
          enter-to-class="opacity-100 translate-y-0"
        >
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>

    <!-- 页脚 -->
    <footer class="no-print border-t border-line bg-white/60">
      <div class="max-w-6xl mx-auto px-4 py-5 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-faint">
        <span>SafeRx 用药安全卫士 · 医疗人工智能课程项目</span>
        <span>数据来源：DDInter 2.0（Nucleic Acids Research 2025, CC BY-NC-SA 4.0）· 非商用 · 匿名运行</span>
      </div>
    </footer>

    <!-- 常驻免责声明条 -->
    <DisclaimerBar />
  </div>
</template>

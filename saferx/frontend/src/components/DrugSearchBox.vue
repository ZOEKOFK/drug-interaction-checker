<script setup>
/**
 * 药物搜索框：模糊搜索（中文/英文/拼音首字母）+ 候选下拉 + 键盘导航
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { searchDrugs } from '../api/client.js'

const props = defineProps({
  placeholder: { type: String, default: '输入药名：中文 / 英文 / 拼音首字母，如 华法林 · warfarin · hfl' },
  size: { type: String, default: 'normal' } // normal | large
})
const emit = defineEmits(['select'])

const query = ref('')
const results = ref([])
const open = ref(false)
const activeIndex = ref(-1)
const root = ref(null)
let debounceTimer = null

function onInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    activeIndex.value = -1
    const list = await searchDrugs(query.value, 8)
    results.value = list
    open.value = true
  }, 180)
}

function select(drug) {
  emit('select', drug)
  query.value = ''
  results.value = []
  open.value = false
}

function onKeydown(e) {
  if (!open.value || results.value.length === 0) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % results.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = activeIndex.value <= 0 ? results.value.length - 1 : activeIndex.value - 1
  } else if (e.key === 'Enter' && activeIndex.value >= 0) {
    e.preventDefault()
    select(results.value[activeIndex.value])
  } else if (e.key === 'Escape') {
    open.value = false
  }
}

function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <div ref="root" class="relative w-full">
    <div
      class="flex items-center gap-2 bg-white border rounded-full transition-shadow shadow-sm"
      :class="[
        size === 'large' ? 'h-14 px-5 text-base' : 'h-11 px-4 text-sm',
        open && results.length ? 'border-primary-bright ring-4 ring-primary-50' : 'border-line focus-within:border-primary-bright focus-within:ring-4 focus-within:ring-primary-50'
      ]"
    >
      <svg class="w-5 h-5 text-ink-faint shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" stroke-linecap="round" />
      </svg>
      <input
        v-model="query"
        :placeholder="placeholder"
        class="flex-1 outline-none bg-transparent min-w-0 placeholder:text-ink-faint/70"
        @input="onInput"
        @keydown="onKeydown"
        @focus="open = results.length > 0 || query ? true : false"
      />
      <button
        v-if="query"
        class="w-6 h-6 rounded-full text-ink-faint hover:text-ink flex items-center justify-center shrink-0"
        @click="query = ''; results = []; open = false"
        title="清空"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 6l12 12M18 6 6 18" stroke-linecap="round" />
        </svg>
      </button>
    </div>

    <!-- 候选下拉 -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="open" class="absolute z-30 mt-2 w-full card overflow-hidden p-1.5 max-h-80 overflow-y-auto">
        <template v-if="results.length">
          <button
            v-for="(d, i) in results"
            :key="d.ddinter_id"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors"
            :class="i === activeIndex ? 'bg-primary-50' : 'hover:bg-primary-50/60'"
            @click="select(d)"
            @mousemove="activeIndex = i"
          >
            <span class="w-8 h-8 rounded-full bg-primary-100 text-primary flex items-center justify-center text-xs font-bold shrink-0">
              {{ d.name_cn.slice(0, 1) }}
            </span>
              <span class="flex-1 min-w-0">
                <span class="block font-semibold text-ink truncate">{{ d.name_cn }}</span>
                <span v-if="d.name_en !== d.name_cn" class="block text-xs text-ink-faint truncate">{{ d.name_en }}<template v-if="d.atc"> · {{ d.atc }}</template></span>
              </span>
              <span v-if="d.category" class="badge badge-clear shrink-0 hidden sm:inline-flex">{{ d.category }}</span>
          </button>
        </template>
        <template v-else-if="query">
          <div class="px-4 py-6 text-center">
            <p class="text-ink-soft text-sm font-medium">未找到「{{ query }}」</p>
            <p class="text-ink-faint text-xs mt-1">请检查药名拼写，或尝试中文通用名 / 英文 / 拼音首字母</p>
          </div>
        </template>
        <div class="px-3 py-1.5 text-[11px] text-ink-faint border-t border-line mt-1" v-if="results.length">
          ↑ ↓ 选择 · Enter 确认 · Esc 关闭
        </div>
      </div>
    </Transition>
  </div>
</template>

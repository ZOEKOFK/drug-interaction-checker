<script setup>
import { ref, computed } from 'vue'
import { extract as apiExtract } from '../api/client.js'
import labSamples from '../assets/sample_meds/lab_samples.json'

const text = ref(labSamples[0].text)
const activeSample = ref(labSamples[0].id)
const extracted = ref(null)
const running = ref(false)

function useSample(s) {
  activeSample.value = s.id
  text.value = s.text
  extracted.value = null
}

async function runExtract() {
  if (!text.value.trim()) return
  running.value = true
  try {
    // 优先走后端 /api/lab/extract（规则基线，后续接入 UIE/BioBERT 模型；离线自动降级）
    extracted.value = await apiExtract(text.value)
  } finally {
    running.value = false
  }
}

/** 高亮分词渲染：库内药物实心高亮，模型识别出但库内无对应的药名用虚线下划线 */
const segments = computed(() => {
  if (!extracted.value) return []
  const { entities } = extracted.value
  const segs = []
  let cursor = 0
  for (const e of entities) {
    if (e.start > cursor) segs.push({ text: text.value.slice(cursor, e.start) })
    segs.push({ text: e.text, drug: e.drug, source: e.source, start: e.start })
    cursor = e.end
  }
  if (cursor < text.value.length) segs.push({ text: text.value.slice(cursor) })
  return segs
})

// 引擎标签：后端会在 engine 里说明这一轮用的是词典还是 BioBERT
const ENGINE_META = {
  biobert: { label: 'BioBERT 序列标注', cls: 'badge-major', tip: '实体 F1 0.877（DDIExtraction 2013）' },
  dict: { label: '词典基线', cls: 'badge-moderate', tip: '实体 F1 0.656，词表外商品名会漏' }
}
const engineMeta = computed(() => ENGINE_META[extracted.value?.engine] || ENGINE_META.dict)
const unknownNames = computed(() => (extracted.value?.unknown_entities || []).map((u) => u.text))

const STATUS_META = {
  known: { label: '主库已收录', cls: 'badge-minor' },
  new: { label: '新增候选', cls: 'badge-moderate' }
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <div class="flex items-start justify-between flex-wrap gap-4">
      <div>
        <h1 class="text-2xl font-extrabold tracking-tight">AI 实验室 · 文献 DDI 抽取</h1>
        <p class="mt-1 text-sm text-ink-soft">
          粘贴药品说明书或文献段落，模型自动识别药物实体并抽取相互作用三元组，与主库比对给出「已收录 / 新增候选」
        </p>
      </div>
      <span class="badge badge-dot" :class="engineMeta.cls" :title="engineMeta.tip">
        识别引擎：{{ engineMeta.label }}
      </span>
    </div>

    <div class="mt-6 grid lg:grid-cols-2 gap-5 items-start">
      <!-- ============ 左：输入与高亮 ============ -->
      <div class="card p-5">
        <div class="flex items-center justify-between flex-wrap gap-2 mb-3">
          <h2 class="font-bold text-sm">输入文本</h2>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="s in labSamples"
              :key="s.id"
              class="px-3 py-1 rounded-full text-xs font-semibold border transition-colors"
              :class="activeSample === s.id ? 'bg-primary text-white border-primary' : 'bg-white text-ink-soft border-line hover:text-primary hover:border-primary-bright'"
              @click="useSample(s)"
            >
              {{ s.title }}
            </button>
          </div>
        </div>

        <textarea
          v-model="text"
          rows="6"
          class="w-full rounded-xl border border-line p-3.5 text-sm leading-relaxed outline-none focus:border-primary-bright focus:ring-4 focus:ring-primary-50 resize-y"
          placeholder="粘贴一段包含药物联用描述的文本…"
        />

        <button class="btn-primary mt-3 w-full" :disabled="running || !text.trim()" @click="runExtract">
          <svg v-if="!running" class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m12 3 1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3Z" stroke-linejoin="round" />
          </svg>
          <svg v-else class="w-[18px] h-[18px] animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M21 12a9 9 0 1 1-6.2-8.6" stroke-linecap="round" />
          </svg>
          {{ running ? '模型推理中…' : '开始抽取' }}
        </button>

        <!-- 实体高亮预览 -->
        <div v-if="extracted" class="mt-4">
          <p class="text-xs font-bold text-ink-faint tracking-wide mb-2">
            实体识别结果（高亮 = 药物实体，共 {{ extracted.entities.length }} 个）
          </p>
          <div class="rounded-xl bg-paper border border-line p-4 text-sm leading-loose">
            <template v-for="(seg, i) in segments" :key="i">
              <mark
                v-if="seg.drug"
                class="bg-primary-100 text-primary-dark rounded px-1 py-0.5 font-semibold"
                :title="`${seg.drug.name_en} · ${seg.drug.category || '未分类'}｜来源：${seg.source === 'model' ? 'BioBERT' : '词典'}`"
              >{{ seg.text }}</mark>
              <span
                v-else-if="seg.source === 'model'"
                class="border-b-2 border-dashed border-line text-ink-soft cursor-help"
                title="模型识别为药物实体，但主库无对应药名——属待评审的库外药名"
              >{{ seg.text }}</span>
              <template v-else>{{ seg.text }}</template>
            </template>
          </div>
          <p v-if="unknownNames.length" class="mt-2 text-xs text-ink-faint">
            库外药名 {{ unknownNames.length }} 个：{{ unknownNames.join('、') }} —— 不计入三元组，建议人工核实后评审入库
          </p>
        </div>
      </div>

      <!-- ============ 右：抽取结果 ============ -->
      <div class="card p-5 min-h-[300px]">
        <h2 class="font-bold text-sm">抽取的三元组（药物 A，药物 B，相互作用）</h2>

        <div v-if="!extracted" class="mt-10 text-center text-ink-faint text-sm">
          <svg class="w-12 h-12 mx-auto mb-3 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M4 19.5V6a2 2 0 0 1 2-2h13v14a2 2 0 0 1-2 2H6.5A2.5 2.5 0 0 1 4 19.5Z" /><path d="M8 8h8M8 12h8M8 16h5" stroke-linecap="round" />
          </svg>
          点击「开始抽取」查看结果
        </div>

        <template v-else>
          <p v-if="!extracted.triples.length" class="mt-8 text-center text-ink-faint text-sm">
            未在文本中发现两种及以上不同药物，无法构成药物对
          </p>

          <div v-else class="mt-3 space-y-3">
            <div v-for="(t, i) in extracted.triples" :key="i" class="p-4 rounded-xl border border-line bg-white">
              <div class="flex items-center justify-between gap-2 flex-wrap">
                <p class="text-sm font-bold text-ink">
                  {{ t.drug_a.name_cn }} <span class="text-ink-faint font-normal text-xs">{{ t.drug_a.name_en }}</span>
                  <span class="mx-1 text-ink-faint">×</span>
                  {{ t.drug_b.name_cn }} <span class="text-ink-faint font-normal text-xs">{{ t.drug_b.name_en }}</span>
                </p>
                <span class="badge badge-dot" :class="STATUS_META[t.status].cls">{{ STATUS_META[t.status].label }}</span>
              </div>
              <div class="mt-2 flex items-center gap-2 flex-wrap">
                <span v-if="t.level" class="badge badge-dot" :class="'badge-' + t.level.toLowerCase()">
                  {{ t.level_cn }}风险
                </span>
                <span class="text-[11px] text-ink-faint">
                  置信度 {{ (t.confidence * 100).toFixed(0) }}%（演示值）· 来源：{{ t.status === 'known' ? '与主库比对一致' : '模型抽取，待人工评审' }}
                </span>
              </div>
              <p class="mt-2 text-xs text-ink-soft leading-relaxed">{{ t.mechanism_cn }}</p>
            </div>
          </div>

          <div class="mt-4 rounded-lg bg-primary-50 p-3 text-[11px] text-ink-soft leading-relaxed">
            「新增候选」表示主库未收录该药物对——NLP 扩库的意义所在：机器从文献中持续挖掘候选记录，
            经人工评审后进入审编数据库，形成「AI 提议 + 人类把关」的闭环。
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 力导向知识图谱（ECharts graph 封装）
 * - 节点 = 药单药物（大小=关联度，描边色=涉及的最高风险级）
 * - 边 = 收录的 DDI 记录（颜色=风险级）
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] },
  onlyMajor: { type: Boolean, default: false }
})
const emit = defineEmits(['node-click'])

const el = ref(null)
let chart = null

function render() {
  if (!chart) return
  const links = props.onlyMajor ? props.links.filter((l) => l.value === 'Major') : props.links
  chart.setOption(
    {
      animationDurationUpdate: 400,
      tooltip: {
        formatter: (p) => {
          if (p.dataType === 'node') {
            return `<b>${p.data.name}</b>（${p.data.name_en}）<br/>类别：${p.data.category}<br/>涉及收录相互作用：${p.data.degree} 条`
          }
          const cn = { Major: '严重', Moderate: '中度', Minor: '轻微', Unknown: '分级未知' }
          return `${p.data.source} — ${p.data.target}<br/><b>${cn[p.data.value]}风险</b>`
        }
      },
      legend: { show: false },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          force: { repulsion: 340, edgeLength: [90, 150], gravity: 0.09, friction: 0.25 },
          emphasis: { focus: 'adjacency', lineStyle: { width: 5 } },
          label: { show: true, position: 'bottom', distance: 4, color: '#1F2A26', fontSize: 12, fontWeight: 600 },
          itemStyle: { color: '#BFE0D6' },
          nodes: props.nodes,
          links
        }
      ]
    },
    { notMerge: true }
  )
}

function bindClick() {
  chart.on('click', (params) => {
    if (params.dataType === 'node') emit('node-click', params.data)
  })
}

onMounted(() => {
  chart = echarts.init(el.value)
  bindClick()
  render()
  const ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
  onBeforeUnmount(() => ro.disconnect())
})
watch(() => [props.nodes, props.links, props.onlyMajor], render, { deep: true })
onBeforeUnmount(() => {
  if (chart) chart.dispose()
})
</script>

<template>
  <div ref="el" class="w-full h-full min-h-[420px]" />
</template>

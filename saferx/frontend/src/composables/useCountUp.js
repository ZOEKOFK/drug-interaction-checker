import { ref, onMounted } from 'vue'

/** 数字滚动动画（首页数据规模展示用） */
export function useCountUp(target, duration = 1400) {
  const value = ref(0)
  onMounted(() => {
    const t0 = performance.now()
    function tick(t) {
      const p = Math.min(1, (t - t0) / duration)
      value.value = Math.round(target * (1 - Math.pow(1 - p, 3))) // easeOutCubic
      if (p < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
  return value
}

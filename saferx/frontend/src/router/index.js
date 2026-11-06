import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { title: '首页 · SafeRx 用药安全卫士' }
  },
  {
    path: '/medications',
    name: 'medications',
    component: () => import('../views/MedicationView.vue'),
    meta: { title: '我的药单 · SafeRx 用药安全卫士' }
  },
  {
    path: '/results',
    name: 'results',
    component: () => import('../views/CheckResultView.vue'),
    meta: { title: '检查结果 · SafeRx 用药安全卫士' }
  },
  {
    path: '/graph',
    name: 'graph',
    component: () => import('../views/GraphView.vue'),
    meta: { title: '交互图谱 · SafeRx 用药安全卫士' }
  },
  {
    path: '/lab',
    name: 'lab',
    component: () => import('../views/LabView.vue'),
    meta: { title: 'AI 实验室 · SafeRx 用药安全卫士' }
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('../views/AboutView.vue'),
    meta: { title: '关于 · SafeRx 用药安全卫士' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.afterEach((to) => {
  document.title = to.meta.title || 'SafeRx 用药安全卫士'
})

export default router

import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

/**
 * 全局前置守卫
 * 1. 未登录访问受保护页面 → 跳登录页（带 redirect）
 * 2. 已登录访问登录页 → 跳首页
 * 3. 已登录但角色无权限 → 提示并回首页
 */
router.beforeEach((to) => {
  const userStore = useUserStore()
  document.title = to.meta?.title ? `${to.meta.title} - 仓储管理系统` : '仓储管理系统'

  // 公开页面（登录页）
  if (to.meta?.public) {
    if (userStore.isLogin) {
      return { path: '/dashboard' }
    }
    return true
  }

  // 未登录
  if (!userStore.isLogin) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 角色权限校验
  const roles = to.meta?.roles
  if (roles && roles.length && !roles.includes(userStore.role)) {
    ElMessage.error('无权限访问该页面')
    return { path: '/dashboard' }
  }

  return true
})

export default router

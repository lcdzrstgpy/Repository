import { defineStore } from 'pinia'
import { login as loginApi, getMe, logout as logoutApi } from '@/api/auth'
import { TOKEN_KEY, USER_KEY } from '@/utils/constants'

/** 从 localStorage 读取已缓存的用户信息 */
function readCachedUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

/**
 * 用户会话 store
 * token 与用户信息都持久化到 localStorage，刷新页面不丢登录态
 */
export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: readCachedUser()
  }),

  getters: {
    /** 角色：admin / operator / warehouse / approver */
    role: (state) => state.user?.role || '',
    username: (state) => state.user?.username || '',
    realName: (state) => state.user?.real_name || state.user?.username || '',
    /** 角色中文名 */
    roleText: (state) => {
      const map = { admin: '管理员', operator: '运营', warehouse: '仓储', approver: '审批' }
      return map[state.user?.role] || '未知角色'
    },
    isAdmin: (state) => state.user?.role === 'admin',
    /** 是否已登录 */
    isLogin: (state) => !!state.token
  },

  actions: {
    /** 保存 token 与用户信息 */
    setSession(token, user) {
      this.token = token || ''
      this.user = user || null
      if (token) {
        localStorage.setItem(TOKEN_KEY, token)
      } else {
        localStorage.removeItem(TOKEN_KEY)
      }
      if (user) {
        localStorage.setItem(USER_KEY, JSON.stringify(user))
      } else {
        localStorage.removeItem(USER_KEY)
      }
    },

    /** 登录 */
    async login(form) {
      const data = await loginApi(form)
      this.setSession(data.access_token, data.user)
      return data
    },

    /** 拉取当前用户信息（刷新页面后校正缓存） */
    async fetchMe() {
      const user = await getMe()
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
      return user
    },

    /** 退出登录 */
    async logout() {
      try {
        await logoutApi()
      } catch (e) {
        // 退出接口失败也要清本地登录态
      }
      this.setSession('', null)
    },

    /** 仅清本地登录态（token 失效时使用） */
    clearSession() {
      this.setSession('', null)
    }
  }
})

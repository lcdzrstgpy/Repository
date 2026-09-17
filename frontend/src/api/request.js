import axios from 'axios'
import { ElMessage } from 'element-plus'
import { TOKEN_KEY, USER_KEY } from '@/utils/constants'

/**
 * Axios 统一封装
 * - 请求拦截：自动带上 Authorization: Bearer <token>
 * - 响应拦截：
 *     code === 0   → 直接返回 data 字段（业务代码不用再 .data.data）
 *     code === 401 → 清 token 并跳登录页
 *     其他 code    → ElMessage.error 弹出 msg
 */
const service = axios.create({
  baseURL: '',
  timeout: 20000
})

/** 清除本地登录态（不依赖 store / router，避免循环引用） */
function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/** 跳转登录页（整页刷新，顺带重置 Pinia） */
function redirectToLogin() {
  clearAuth()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => {
    const res = response.data

    // 后端未按统一格式返回（例如文件流）时原样返回
    if (res === null || typeof res !== 'object' || !('code' in res)) {
      return res
    }

    if (res.code === 0) {
      return res.data
    }

    if (res.code === 401) {
      ElMessage.error(res.msg || '登录已失效，请重新登录')
      redirectToLogin()
      return Promise.reject(new Error(res.msg || '登录已失效'))
    }

    ElMessage.error(res.msg || '请求失败')
    return Promise.reject(new Error(res.msg || '请求失败'))
  },
  (error) => {
    // HTTP 层错误（后端异常、网络不通等）
    const status = error.response?.status
    const msg = error.response?.data?.msg

    if (status === 401) {
      ElMessage.error(msg || '登录已失效，请重新登录')
      redirectToLogin()
      return Promise.reject(error)
    }

    if (status === 403) {
      ElMessage.error(msg || '无权限执行该操作')
      return Promise.reject(error)
    }

    if (msg) {
      ElMessage.error(msg)
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请稍后重试')
    } else if (error.message === 'Network Error') {
      ElMessage.error('无法连接服务器，请确认后端服务已启动')
    } else {
      ElMessage.error('请求失败，请稍后重试')
    }
    return Promise.reject(error)
  }
)

export default service

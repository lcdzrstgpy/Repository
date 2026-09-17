import axios from 'axios'
import { ElMessage } from 'element-plus'
import { TOKEN_KEY, USER_KEY } from '@/utils/constants'

/**
 * 文件下载专用封装（契约 14.1）
 *
 * 为什么不用 request.js：
 *   request.js 的响应拦截器按统一格式 { code, msg, data } 解析，遇到 code=0 会返回 data 字段，
 *   而导出接口直接返回 xlsx 二进制流（无包装），走那套逻辑会把 Blob 破坏掉。
 *   因此这里独立建一个 axios 实例，自己处理响应与错误。
 */
const downloadService = axios.create({
  baseURL: '',
  // 导出数据量可能较大，超时给长一些
  timeout: 60000
})

/** 清除本地登录态（与 request.js 保持一致，不依赖 store / router 避免循环引用） */
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

// 请求拦截：手动带上 Authorization 头
downloadService.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

/**
 * 从 Content-Disposition 解析文件名
 * 兼容两种写法：
 *   filename="xxx.xlsx"                    （普通写法，可能带 URL 编码）
 *   filename*=UTF-8''%E5%95%86%E5%93%81.xlsx（RFC 5987 写法）
 * @param {string} disposition 响应头
 * @param {string} fallbackName 解析不到时使用的兜底文件名
 */
export function parseFileName(disposition, fallbackName = '导出文件.xlsx') {
  if (!disposition) return fallbackName

  // 优先取 filename*（RFC 5987），它的编码方式更可靠
  const starMatch = disposition.match(/filename\*\s*=\s*([^;]+)/i)
  if (starMatch) {
    let value = starMatch[1].trim().replace(/^["']|["']$/g, '')
    // 形如 UTF-8''xxx，去掉字符集与语言声明
    const sepIndex = value.indexOf("''")
    if (sepIndex !== -1) {
      value = value.slice(sepIndex + 2)
    }
    return safeDecode(value) || fallbackName
  }

  const plainMatch = disposition.match(/filename\s*=\s*([^;]+)/i)
  if (plainMatch) {
    const value = plainMatch[1].trim().replace(/^["']|["']$/g, '')
    return safeDecode(value) || fallbackName
  }

  return fallbackName
}

/** decodeURIComponent 的容错版：解码失败（含非法 % 序列）时原样返回 */
function safeDecode(value) {
  if (!value) return ''
  try {
    return decodeURIComponent(value)
  } catch (e) {
    return value
  }
}

/** Blob 转文本，用于读取后端在 blob 里返回的 JSON 错误信息 */
function blobToText(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => resolve('')
    reader.readAsText(blob, 'utf-8')
  })
}

/** 尝试把文本解析成 JSON 并取出 msg 字段，解析不出来返回空串 */
function parseJsonMessage(text) {
  if (!text) return ''
  try {
    const json = JSON.parse(text)
    return json?.msg || json?.message || ''
  } catch (e) {
    return ''
  }
}

/** 触发浏览器下载：创建隐藏 <a> 点击后释放对象 URL */
function saveBlob(blob, fileName) {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = fileName
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  // 下载已触发，释放对象 URL 避免内存泄漏
  URL.revokeObjectURL(objectUrl)
}

/** 从错误响应里提取提示文案（导出接口出错时后端可能返回 blob 包着的 JSON） */
async function extractErrorMessage(error) {
  const status = error.response?.status
  const data = error.response?.data

  if (data instanceof Blob) {
    const msg = parseJsonMessage(await blobToText(data))
    if (msg) return msg
  }
  if (data && typeof data === 'object' && data.msg) {
    return data.msg
  }

  if (status === 401) return '登录已失效，请重新登录'
  if (status === 403) return '无权限执行该操作'
  if (status === 404) return '导出接口不存在，请联系管理员'
  if (error.code === 'ECONNABORTED') return '导出超时，请稍后重试'
  if (error.message === 'Network Error') return '无法连接服务器，请确认后端服务已启动'
  return '导出失败，请稍后重试'
}

/**
 * 通用文件下载
 * @param {string} url 接口路径
 * @param {Object} params query 参数
 * @param {string} fallbackName 后端未给文件名时的兜底名
 * @returns {Promise<string>} 实际保存的文件名
 */
export async function downloadFile(url, params = {}, fallbackName = '导出文件.xlsx') {
  let response
  try {
    response = await downloadService.get(url, {
      params,
      responseType: 'blob'
    })
  } catch (error) {
    const msg = await extractErrorMessage(error)
    if (error.response?.status === 401) {
      ElMessage.error(msg)
      redirectToLogin()
    } else {
      ElMessage.error(msg)
    }
    throw new Error(msg)
  }

  const blob = response.data
  const contentType = response.headers['content-type'] || ''

  // 兜底：HTTP 200 但返回的是 JSON（blob 类型但内容是 JSON 错误），读出内容提示
  if (contentType.includes('application/json') || blob?.type?.includes('application/json')) {
    const msg = parseJsonMessage(await blobToText(blob)) || '导出失败，请稍后重试'
    ElMessage.error(msg)
    throw new Error(msg)
  }

  const fileName = parseFileName(response.headers['content-disposition'], fallbackName)
  saveBlob(blob, fileName)
  return fileName
}

export default downloadFile

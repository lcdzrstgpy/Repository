import { useAuthStore } from '../store/auth'
import type { AuthResponse, Category, CreateSubmissionPayload, Sku, Submission, SubmissionFilters } from '../types'
import { demoApi } from './demo'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
const DEMO_ENABLED = import.meta.env.DEV && import.meta.env.VITE_DEMO_FALLBACK !== 'false'

export class ApiError extends Error {
  constructor(message: string, public status: number, public details?: unknown) {
    super(message)
  }
}

const camelKey = (key: string) => key.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase())
const snakeKey = (key: string) => key.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`)

function mapKeys(value: unknown, keyMapper: (key: string) => string): unknown {
  if (Array.isArray(value)) return value.map((item) => mapKeys(item, keyMapper))
  if (value && typeof value === 'object' && !(value instanceof Date)) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [keyMapper(key), mapKeys(item, keyMapper)]),
    )
  }
  return value
}

const toCamel = <T,>(value: unknown): T => mapKeys(value, camelKey) as T
const toSnake = (value: unknown) => mapKeys(value, snakeKey)

async function request<T>(path: string, init: RequestInit = {}, fallback?: () => T | Promise<T>): Promise<T> {
  const token = useAuthStore.getState().token
  try {
    const body = typeof init.body === 'string' ? JSON.stringify(toSnake(JSON.parse(init.body))) : init.body
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      body,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
    if (response.status === 401) {
      useAuthStore.getState().logout()
      throw new ApiError('登录已过期，请重新登录', 401)
    }
    if (!response.ok) {
      const responseBody = await response.json().catch(() => null) as { message?: string; detail?: string } | null
      throw new ApiError(responseBody?.message ?? responseBody?.detail ?? '请求失败', response.status, responseBody)
    }
    if (response.status === 204) return undefined as T
    return toCamel<T>(await response.json())
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (DEMO_ENABLED && fallback) {
      window.dispatchEvent(new CustomEvent('demo-fallback'))
      await new Promise((resolve) => setTimeout(resolve, 220))
      return fallback()
    }
    throw new ApiError(error instanceof Error ? error.message : '网络连接失败', 0)
  }
}

const queryString = (params: Record<string, string | boolean | undefined>) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') search.set(key, String(value)) })
  return search.size ? `?${search.toString()}` : ''
}

export const api = {
  auth: {
    login: async (username: string, password: string) => {
      if (DEMO_ENABLED) {
        try {
          const token = await request<{ accessToken: string; role: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
          return { accessToken: token.accessToken, expiresIn: 480 * 60, user: { id: username, username, displayName: username, role: 'operator' } } as AuthResponse
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 0) throw error
          return demoApi.login(username, password)
        }
      }
      const token = await request<{ accessToken: string; role: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
      return { accessToken: token.accessToken, expiresIn: 480 * 60, user: { id: username, username, displayName: username, role: 'operator' } } as AuthResponse
    },
  },
  catalog: {
    searchSkus: (query: string) => request<Sku[]>(`/catalog/skus/search${queryString({ q: query })}`, {}, () => demoApi.searchSkus(query)),
    categories: () => request<Category[]>('/catalog/categories', {}, () => demoApi.categories()),
  },
  submissions: {
    create: (payload: CreateSubmissionPayload) => request<Submission>('/submissions', { method: 'POST', body: JSON.stringify(payload) }, () => demoApi.create(payload)),
    list: (filters: SubmissionFilters) => request<Submission[]>(`/submissions${queryString({ status: filters.status, order_no: filters.orderNo, has_shortage: filters.shortageOnly })}`, {}, () => demoApi.list(filters)),
    detail: (id: number) => request<Submission>(`/submissions/${id}`, {}, () => demoApi.detail(id)),
    confirmSkus: (id: number) => request<Submission>(`/submissions/${id}/confirm-items`, { method: 'POST' }, () => demoApi.confirmSkus(id)),
    rejectOrder: (id: number, orderId: number, reason: string) => request<Submission>(`/submissions/${id}/orders/${orderId}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }, () => demoApi.rejectOrder(id, orderId, reason)),
    lockQuantities: (id: number, quantities: Array<{ lineId: number; qty: number }>) => request<Submission>(`/submissions/${id}/confirm-quantities`, { method: 'POST', body: JSON.stringify({ quantities }) }, () => demoApi.lockQuantities(id, quantities)),
    cancel: (id: number, reason: string) => request<Submission>(`/submissions/${id}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) }, () => demoApi.cancel(id)),
  },
}

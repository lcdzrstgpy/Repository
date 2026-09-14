import type { Submission, SubmissionStatus } from '../types'

export const STATUS_META: Record<SubmissionStatus, { label: string; tone: string }> = {
  1: { label: '待仓库处理', tone: 'blue' },
  2: { label: '待确认货号', tone: 'amber' },
  3: { label: '待填写数量', tone: 'violet' },
  4: { label: '待作业', tone: 'cyan' },
  5: { label: '作业中', tone: 'cyan' },
  6: { label: '已发货', tone: 'green' },
  CANCELLED: { label: '已取消', tone: 'muted' },
}

export function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

export function timeoutLevel(submission: Submission) {
  if (typeof submission.status !== 'number' || submission.status >= 5) return 0
  const hours = (Date.now() - new Date(submission.statusEnteredAt).getTime()) / 3_600_000
  return hours >= 2 ? 2 : hours >= 1 ? 1 : 0
}

export function timeoutText(submission: Submission) {
  const level = timeoutLevel(submission)
  if (!level) return '正常'
  const minutes = Math.floor((Date.now() - new Date(submission.statusEnteredAt).getTime()) / 60_000)
  return level === 2 ? `超时 ${Math.floor(minutes / 60)}小时${minutes % 60}分` : `已等待 ${minutes} 分钟`
}

export function orderProgress(submission: Submission) {
  const shipped = submission.orders.filter((order) => order.status === 'shipped').length
  const shortage = submission.orders.filter((order) => order.status === 'shortage').length
  return { shipped, shortage, total: submission.orders.length }
}

export function createKey() {
  return crypto.randomUUID()
}

export async function createIdempotencyKey(orderNos: string[]) {
  const source = `${Date.now()}:${orderNos.sort().join('|')}`
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source))
  const hash = Array.from(new Uint8Array(bytes)).map((byte) => byte.toString(16).padStart(2, '0')).join('')
  return `ops-${Date.now()}-${hash.slice(0, 20)}`
}

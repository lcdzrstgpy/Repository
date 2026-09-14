import type { ConfirmStatus, OrderStatus, SubmissionStatus } from '../types'
import { STATUS_META } from '../utils/format'

const ORDER_META: Record<OrderStatus, { label: string; tone: string }> = {
  pending: { label: '未下单', tone: 'muted' },
  ordered: { label: '作业中', tone: 'cyan' },
  shortage: { label: '缺货待补货', tone: 'red' },
  shipped: { label: '已发货', tone: 'green' },
  cancelled: { label: '已取消', tone: 'muted' },
}

const CONFIRM_META: Record<ConfirmStatus, { label: string; tone: string }> = {
  pending: { label: '待确认', tone: 'amber' },
  confirmed: { label: '已确认', tone: 'green' },
  rejected: { label: '已驳回', tone: 'red' },
}

export function StatusBadge({ status }: { status: SubmissionStatus }) {
  const meta = STATUS_META[status]
  return <span className={`badge badge-${meta.tone}`}><i />{typeof status === 'number' ? `${status} · ` : ''}{meta.label}</span>
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const meta = ORDER_META[status]
  return <span className={`badge badge-${meta.tone}`}><i />{meta.label}</span>
}

export function ConfirmBadge({ status }: { status: ConfirmStatus }) {
  const meta = CONFIRM_META[status]
  return <span className={`badge badge-${meta.tone}`}><i />{meta.label}</span>
}

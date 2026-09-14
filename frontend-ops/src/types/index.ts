export type SubmissionStatus = 1 | 2 | 3 | 4 | 5 | 6 | 'CANCELLED'
export type OrderStatus = 'pending' | 'ordered' | 'shortage' | 'shipped' | 'cancelled'
export type ConfirmStatus = 'pending' | 'confirmed' | 'rejected'

export interface User {
  id: string
  username: string
  displayName: string
  role: 'operator'
}

export interface AuthResponse {
  accessToken: string
  expiresIn: number
  user: User
}

export interface Category {
  id: number
  categoryName: string
  parentId: number | null
  codePrefix: string | null
  children?: Category[]
}

export interface Sku {
  id: number
  skuCode: string
  itemName: string
  categoryId: number
  categoryPath: string
  codeStatus: 'active'
}

export interface SubmissionLine {
  id: number
  lineNo: number
  itemId: number | null
  skuCode: string | null
  itemName: string | null
  itemDesc: string | null
  isNewItem: boolean
  categoryId: number | null
  categoryPath: string | null
  draftSkuCode: string | null
  qty: number | null
  qtyLockedAt: string | null
  lineStatus: 'pending' | 'rejected' | 'confirmed'
  rejectReason: string | null
}

export interface SubmissionOrder {
  id: number
  orderNo: string
  status: OrderStatus
  confirmStatus: ConfirmStatus
  rejectCount: number
  shortageAt?: string | null
  shippedAt?: string | null
  lines: SubmissionLine[]
}

export interface TimelineEvent {
  key: string
  label: string
  time: string | null
  detail?: string
  active?: boolean
  done?: boolean
}

export interface Submission {
  id: number
  submissionNo: string
  status: SubmissionStatus
  remark: string | null
  submittedBy: string
  submittedAt: string
  statusEnteredAt: string
  alert1hAt: string | null
  alert2hAt: string | null
  completedAt: string | null
  orders: SubmissionOrder[]
  timeline: TimelineEvent[]
}

export interface SubmissionFilters {
  status?: string
  orderNo?: string
  shortageOnly?: boolean
  from?: string
  to?: string
}

export interface DraftLine {
  key: string
  itemId: number | null
  skuCode: string
  itemDesc: string
  isNewItem: boolean
  categoryId: number | null
}

export interface DraftOrder {
  key: string
  orderNo: string
  lines: DraftLine[]
}

export interface CreateSubmissionPayload {
  idempotencyKey: string
  remark?: string
  orders: Array<{
    orderNo: string
    lines: Array<{
      itemId: number | null
      itemDesc?: string
      isNewItem: boolean
      categoryId: number | null
    }>
  }>
}

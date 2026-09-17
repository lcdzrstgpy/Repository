/**
 * 全局常量与枚举映射
 * 严格对应《接口契约》第三节「枚举定义」，不得自行更改取值
 */

/** localStorage 键名 */
export const TOKEN_KEY = 'warehouse_erp_token'
export const USER_KEY = 'warehouse_erp_user'

/** 用户角色（契约 3.1） */
export const ROLE_MAP = {
  admin: '管理员',
  operator: '运营',
  warehouse: '仓储',
  approver: '审批'
}

export const ROLE_OPTIONS = Object.entries(ROLE_MAP).map(([value, label]) => ({
  value,
  label
}))

/** 订单状态（契约 3.2）：发货即已完成，不再有「已发货」中间态 */
export const ORDER_STATUS = {
  10: { label: '待接单', type: 'info' },
  20: { label: '已接单', type: 'primary' },
  25: { label: '数量待确认', type: 'warning' },
  30: { label: '备货中', type: 'primary' },
  50: { label: '已完成', type: 'success' },
  90: { label: '已取消', type: 'danger' }
}

export const ORDER_STATUS_OPTIONS = Object.entries(ORDER_STATUS).map(([value, item]) => ({
  value: Number(value),
  label: item.label
}))

/** 可取消的状态：10 / 20 / 25 / 30（契约 18） */
export const CANCELABLE_STATUS = [10, 20, 25, 30]

/** 审批状态（契约 3.3） */
export const AUDIT_STATUS_MAP = {
  0: '未审批',
  1: '已审批'
}

/** 往来单位类型（契约 3.4） */
export const PARTNER_TYPE_MAP = {
  1: '客户',
  2: '供应商',
  3: '客户/供应商'
}

export const PARTNER_TYPE_OPTIONS = Object.entries(PARTNER_TYPE_MAP).map(([value, label]) => ({
  value: Number(value),
  label
}))

/** 通用启用状态（契约 3.5） */
export const COMMON_STATUS_MAP = {
  1: '启用',
  0: '停用'
}

export const COMMON_STATUS_OPTIONS = [
  { value: 1, label: '启用' },
  { value: 0, label: '停用' }
]

/** 出库单状态（契约 9.2） */
export const OUT_STATUS = {
  10: { label: '草稿', type: 'info' },
  20: { label: '已完成', type: 'success' },
  90: { label: '已作废', type: 'danger' }
}

export const OUT_STATUS_OPTIONS = Object.entries(OUT_STATUS).map(([value, item]) => ({
  value: Number(value),
  label: item.label
}))

/** 采购单状态（契约 10.2） */
export const PURCHASE_STATUS = {
  10: { label: '待审批', type: 'warning' },
  20: { label: '已审批', type: 'primary' },
  30: { label: '已入库', type: 'success' },
  90: { label: '已取消', type: 'danger' }
}

export const PURCHASE_STATUS_OPTIONS = Object.entries(PURCHASE_STATUS).map(([value, item]) => ({
  value: Number(value),
  label: item.label
}))

/** 采购入库单状态（契约 10.2：简化为创建即入库，固定 20） */
export const PURCHASE_IN_STATUS = {
  20: { label: '已完成', type: 'success' }
}

/** 库存变动类型（契约 9.4） */
export const ORDER_TYPE_MAP = {
  SALES_OUT: '销售出库',
  PURCHASE_IN: '采购入库',
  ADJUST: '库存调整'
}

/** 订单状态时间线步骤（待接单 → 已接单 → 备货中 → 已完成） */
export const ORDER_STEPS = [
  { status: 10, label: '待接单' },
  { status: 20, label: '已接单' },
  { status: 30, label: '备货中' },
  { status: 50, label: '已完成' }
]

/** 根据订单状态取标签文案 */
export function orderStatusLabel(status) {
  return ORDER_STATUS[status]?.label || '未知状态'
}

/** 根据订单状态取 el-tag 类型 */
export function orderStatusType(status) {
  return ORDER_STATUS[status]?.type || 'info'
}

/** 根据出库单状态取标签文案 */
export function outStatusLabel(status) {
  return OUT_STATUS[status]?.label || '未知状态'
}

/** 根据出库单状态取 el-tag 类型 */
export function outStatusType(status) {
  return OUT_STATUS[status]?.type || 'info'
}

/** 根据采购单状态取标签文案 */
export function purchaseStatusLabel(status) {
  return PURCHASE_STATUS[status]?.label || '未知状态'
}

/** 根据采购单状态取 el-tag 类型 */
export function purchaseStatusType(status) {
  return PURCHASE_STATUS[status]?.type || 'info'
}

/** 库存变动类型中文名，未知取值原样返回 */
export function orderTypeLabel(type) {
  if (!type) return '-'
  return ORDER_TYPE_MAP[type] || type
}

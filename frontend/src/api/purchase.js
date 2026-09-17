import request from './request'

/**
 * 三阶段 · 采购
 * 契约 10.3
 */

/** 创建采购单 */
export function createPurchaseOrder(data) {
  return request.post('/api/purchase-orders', data)
}

/** 库存不足的备货订单及其自动计算出的采购明细。 */
export function getPurchaseCandidates() {
  return request.get('/api/purchase-orders/candidates')
}

/** 采购单列表，支持 ?page=&page_size=&status=&keyword= */
export function getPurchaseList(params) {
  return request.get('/api/purchase-orders', { params })
}

/** 采购单详情（含明细 items） */
export function getPurchaseDetail(id) {
  return request.get(`/api/purchase-orders/${id}`)
}

/** 审批通过：status 10 → 20（approver / admin） */
export function approvePurchaseOrder(id) {
  return request.post(`/api/purchase-orders/${id}/approve`, {})
}

/** 取消采购单：status 10 / 20 → 90 */
export function cancelPurchaseOrder(id) {
  return request.post(`/api/purchase-orders/${id}/cancel`, {})
}

/**
 * 收货入库：增加库存并生成入库单
 * @param {Object} data { remark, items: [{ order_item_id, count }] }
 */
export function receivePurchaseOrder(id, data) {
  return request.post(`/api/purchase-orders/${id}/receive`, data)
}

/** 采购入库单列表 */
export function getPurchaseInList(params) {
  return request.get('/api/purchase-ins', { params })
}

/** 采购入库单详情（含明细 items） */
export function getPurchaseInDetail(id) {
  return request.get(`/api/purchase-ins/${id}`)
}

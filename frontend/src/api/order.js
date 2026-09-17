import request from './request'

/**
 * 运营侧 · 销售订单
 * 契约 5.3
 */

/** 创建订单 */
export function createOrder(data) {
  return request.post('/api/sales-orders', data)
}

/** 订单列表（operator 只返回自己创建的；admin/warehouse 返回全部） */
export function getOrderList(params) {
  return request.get('/api/sales-orders', { params })
}

/** 订单详情（含明细 items） */
export function getOrderDetail(id) {
  return request.get(`/api/sales-orders/${id}`)
}

/** 取消订单（仅 status 10/20/30 可取消） */
export function cancelOrder(id, cancelReason) {
  return request.post(`/api/sales-orders/${id}/cancel`, { cancel_reason: cancelReason })
}

/** 确认完成（仅 status 40） */
export function confirmOrder(id) {
  return request.post(`/api/sales-orders/${id}/confirm`, {})
}

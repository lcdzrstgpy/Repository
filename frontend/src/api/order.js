import request from './request'

/**
 * 运营侧 · 销售订单
 * 契约 5.3 / 19.1（六阶段订单模型重构后，创建订单请求体以 19.1 为准）
 */

/**
 * 创建订单
 * 请求体（契约 19.1）：
 * {
 *   no: 'TB20260917001',                    // 运营录入的外部平台订单号，必填且全局唯一
 *   remark: '加急',                          // 选填
 *   items: [
 *     { product_name: '蓝牙耳机', sku_code: 'HW-001', count: 2, expect_price: 35.00 },
 *     { product_name: '手机壳', is_new: 1, count: 5, expect_price: 8.50 }
 *   ]
 * }
 * 说明：每行 sku_code / is_new 二选一；total_count / total_price 由后端汇总，前端不传。
 */
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

/** 取消订单（仅 status 10/20/25/30 可取消） */
export function cancelOrder(id, cancelReason) {
  return request.post(`/api/sales-orders/${id}/cancel`, { cancel_reason: cancelReason })
}

/**
 * 确认数量（契约 19.6）
 * 运营确认数量，订单从「数量待确认」(25) 流转到「备货中」(30)，同时由后端预留库存。
 * `payload.items` 必须包含每个订单明细的最终数量；不校验库存，确认后由仓储备货或采购。
 */
export function confirmQuantity(orderId, payload) {
  return request.post(`/api/sales-orders/${orderId}/confirm-quantity`, payload)
}

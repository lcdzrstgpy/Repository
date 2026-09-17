import request from './request'

/**
 * 仓储侧 · 订单处理
 * 契约 5.4 / 19.2
 */

/** 待接单列表（status = 10，全部运营的订单） */
export function getPendingOrders(params) {
  return request.get('/api/warehouse/pending-orders', { params })
}

/** 接单（仅 status 10，成功后 status = 20） */
export function claimOrder(id, warehouseId) {
  return request.post(`/api/warehouse/orders/${id}/claim`, { warehouse_id: warehouseId })
}

/**
 * 货号处理：为订单明细行关联已有货号或新建货号（契约 19.2 / 19.7）
 * 仅 status = 20（已接单）可调用；已关联过的行不可再次修改。
 * 绑完该订单所有明细行的货号后，后端自动把订单流转到 25（数量待确认）。
 *
 * payload.items 每个元素二选一：
 *   { item_id: 1, sku_code: 'HW-001' }                                  // 关联已有
 *   { item_id: 2, new_sku: { sku_code, product_name, spec, price } }     // 新建
 */
export function bindSku(orderId, payload) {
  return request.post(`/api/warehouse/orders/${orderId}/bind-sku`, payload)
}

/** 发货（仅 status 30，成功后 status = 40，回传点） */
export function shipOrder(id, expressNo) {
  return request.post(`/api/warehouse/orders/${id}/ship`, { express_no: expressNo })
}

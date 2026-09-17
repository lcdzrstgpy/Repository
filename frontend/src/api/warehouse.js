import request from './request'

/**
 * 仓储侧 · 订单处理
 * 契约 5.4 / 19.2
 */

/** 待接单列表（status = 10，全部运营的订单） */
export function getPendingOrders(params) {
  return request.get('/api/warehouse/pending-orders', { params })
}

/** 待备货订单按货号汇总的采购需求。 */
export function getPurchaseSummary() {
  return request.get('/api/warehouse/purchase-summary')
}

/** 备货中订单：按可完整发货优先级排序。 */
export function getPreparingOrders(params) {
  return request.get('/api/warehouse/preparing-orders', { params })
}

/** 仓储货号管理：查询与按三级分类自动生成货号。 */
export function getItemNumbers() {
  return request.get('/api/warehouse/item-numbers')
}
export function createItemNumber(data) {
  return request.post('/api/warehouse/item-numbers', data)
}

export function updateItemNumberStatus(id, status) {
  return request.patch(`/api/warehouse/item-numbers/${id}/status`, { status })
}

/** 接单（仅 status 10，成功后 status = 20） */
export function claimOrder(id) {
  return request.post(`/api/warehouse/orders/${id}/claim`, {})
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

/** 发货（仅 status 30，成功后 status = 50 已完成：发完即终态，运营无需再确认） */
export function shipOrder(id, expressNo) {
  return request.post(`/api/warehouse/orders/${id}/ship`, { express_no: expressNo })
}

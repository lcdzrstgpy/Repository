import request from './request'

/**
 * 二阶段 · 出库单与库存调整
 * 契约 9.4
 */

/** 出库单列表，支持 ?page=&page_size=&keyword= */
export function getOutList(params) {
  return request.get('/api/sales-outs', { params })
}

/** 出库单详情（含明细 items） */
export function getOutDetail(id) {
  return request.get(`/api/sales-outs/${id}`)
}

/** 作废出库单：回滚库存，关联订单状态回退到「备货中」 */
export function cancelOut(id) {
  return request.post(`/api/sales-outs/${id}/cancel`, {})
}

/**
 * 手动调整库存（仓储、管理员）
 * @param {Object} data { sku_id, quantity, remark }
 *   quantity 为目标值，后端算差异后走 change_inventory
 */
export function adjustInventory(data) {
  return request.post('/api/inventory/adjust', data)
}

/** 采购或提前备货入库（仓储、管理员）。quantity 为本次增加量。 */
export function inboundInventory(data) {
  return request.post('/api/inventory/inbound', data)
}

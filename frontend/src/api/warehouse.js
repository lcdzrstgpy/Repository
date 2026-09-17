import request from './request'

/**
 * 仓储侧 · 订单处理
 * 契约 5.4
 */

/** 待接单列表（status = 10，全部运营的订单） */
export function getPendingOrders(params) {
  return request.get('/api/warehouse/pending-orders', { params })
}

/** 接单（仅 status 10，成功后 status = 20） */
export function claimOrder(id, warehouseId) {
  return request.post(`/api/warehouse/orders/${id}/claim`, { warehouse_id: warehouseId })
}

/** 开始备货（仅 status 20，成功后 status = 30） */
export function prepareOrder(id) {
  return request.post(`/api/warehouse/orders/${id}/prepare`, {})
}

/** 发货（仅 status 30，成功后 status = 40，回传点） */
export function shipOrder(id, expressNo) {
  return request.post(`/api/warehouse/orders/${id}/ship`, { express_no: expressNo })
}

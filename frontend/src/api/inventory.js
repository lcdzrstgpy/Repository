import request from './request'

/**
 * 库存查询（一阶段只读）
 * 契约 5.5
 */

/** 库存列表 */
export function getInventoryList(params) {
  return request.get('/api/inventory', { params })
}

/** 库存流水 */
export function getInventoryHistory(params) {
  return request.get('/api/inventory/history', { params })
}

/**
 * 库存预警列表（契约 18.3）
 * 支持 ?page=&page_size=
 * 筛选：min_stock > 0 且 可用量 < min_stock，按短缺量从大到小
 */
export function getInventoryAlerts(params) {
  return request.get('/api/inventory/alerts', { params })
}

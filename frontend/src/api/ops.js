import request from './request'

/**
 * 五阶段 · 移库单与盘点单
 * 契约 16.3 / 17.3
 */

// ---------- 移库单 ----------

/** 创建移库单（草稿） */
export function createTransfer(data) {
  return request.post('/api/stock-transfers', data)
}

/** 移库单列表，支持 ?page=&page_size=&keyword=&status= */
export function getTransferList(params) {
  return request.get('/api/stock-transfers', { params })
}

/** 移库单详情（含明细 items） */
export function getTransferDetail(id) {
  return request.get(`/api/stock-transfers/${id}`)
}

/** 执行移库：草稿 → 已完成，出库仓扣减、入库仓增加 */
export function finishTransfer(id) {
  return request.post(`/api/stock-transfers/${id}/finish`, {})
}

/** 作废移库单：仅草稿 → 已作废，不动库存 */
export function cancelTransfer(id) {
  return request.post(`/api/stock-transfers/${id}/cancel`, {})
}

// ---------- 盘点单 ----------

/** 新建盘点单，sku_ids 不传或为空表示整仓盘点 */
export function createStockTake(data) {
  return request.post('/api/stock-takes', data)
}

/** 盘点单列表，支持 ?page=&page_size=&keyword=&status=&warehouse_id= */
export function getStockTakeList(params) {
  return request.get('/api/stock-takes', { params })
}

/** 盘点单详情（含明细 items） */
export function getStockTakeDetail(id) {
  return request.get(`/api/stock-takes/${id}`)
}

/**
 * 录入实盘数量（仅「盘点中」可录入，允许部分录入）
 * @param {Object} data { items: [{ item_id, actual_quantity, remark }] }
 */
export function updateStockTakeItems(id, data) {
  return request.put(`/api/stock-takes/${id}/items`, data)
}

/** 完成盘点：按差异调整库存，盘点中 → 已完成 */
export function finishStockTake(id) {
  return request.post(`/api/stock-takes/${id}/finish`, {})
}

/** 作废盘点单：仅盘点中 → 已作废，不动库存 */
export function cancelStockTake(id) {
  return request.post(`/api/stock-takes/${id}/cancel`, {})
}

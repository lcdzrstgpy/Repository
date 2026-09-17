import { downloadFile } from './download'

/**
 * 四阶段 · Excel 导出（契约 14.1）
 * 导出接口直接返回 xlsx 文件流，不走统一 { code, msg, data } 包装，
 * 因此统一调用 download.js 的通用下载函数。
 */

/** 导出商品列表（仅 admin） */
export function exportProducts() {
  return downloadFile('/api/export/products', {}, '商品列表.xlsx')
}

/** 导出 SKU 列表（仅 admin） */
export function exportSkus() {
  return downloadFile('/api/export/skus', {}, 'SKU列表.xlsx')
}

/**
 * 导出库存（warehouse / admin）
 * @param {Object} params 当前筛选条件
 */
export function exportInventory(params = {}) {
  return downloadFile('/api/export/inventory', params, '库存列表.xlsx')
}

/**
 * 导出销售订单（operator / warehouse / admin，operator 只导出自己创建的）
 * @param {Object} params 支持 status / start_date / end_date
 */
export function exportSalesOrders(params = {}) {
  return downloadFile('/api/export/sales-orders', params, '销售订单列表.xlsx')
}

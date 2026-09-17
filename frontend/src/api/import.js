import request from './request'

/**
 * 四阶段 · Excel 导入（契约 14.2）
 * 导入接口返回标准 JSON 响应（含导入结果统计），走普通 request.js 实例即可。
 */

/**
 * 批量导入商品（仅 admin）
 * @param {File} file 仅支持 .xlsx 文件
 * @returns {Promise<Object>} { total, success, failed, errors: [{ row, message }] }
 */
export function importProducts(file) {
  const formData = new FormData()
  // 字段名固定为 file（契约 14.2）
  formData.append('file', file)
  // 不手动设置 Content-Type，交给 axios 自动补 multipart boundary
  return request.post('/api/import/products', formData)
}

import request from './request'

/**
 * 五组基础数据接口结构完全一致，用工厂函数生成
 * 契约：GET 列表 / GET 详情 / POST 新增 / PUT 修改 / DELETE 删除（软删）
 */
function createCrudApi(resource) {
  return {
    list: (params) => request.get(`/api/${resource}`, { params }),
    detail: (id) => request.get(`/api/${resource}/${id}`),
    create: (data) => request.post(`/api/${resource}`, data),
    update: (id, data) => request.put(`/api/${resource}/${id}`, data),
    remove: (id) => request.delete(`/api/${resource}/${id}`)
  }
}

/** 仓库 */
export const warehouseApi = createCrudApi('warehouses')
/** 商品 */
export const productApi = createCrudApi('products')
/** SKU */
export const skuApi = createCrudApi('skus')
/** 用户 */
export const userApi = createCrudApi('users')

/**
 * 采购单供应商下拉选项，type 可选（1 客户 / 2 供应商 / 3 两者）。
 * 管理端已不提供往来单位管理页，但采购流程仍依赖供应商基础数据。
 */
export function getPartnerOptions(type) {
  return request.get('/api/partners/options', { params: type ? { type } : {} })
}

/** SKU 下拉选项（含 sku_code / name / spec / price） */
export function getSkuOptions() {
  return request.get('/api/skus/options')
}

/** 仓库下拉选项 */
export function getWarehouseOptions() {
  return request.get('/api/warehouses/options')
}

/** 运营货号库存查询：只读展示各仓库库存余额。 */
export function queryItems(keyword) {
  return request.get('/api/item-query', { params: keyword ? { keyword } : {} })
}

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')
const [purchaseCreate, receiveDialog, purchaseList, inventoryList, routes] = await Promise.all([
  read('../src/views/warehouse/PurchaseCreate.vue'),
  read('../src/views/warehouse/components/ReceiveDialog.vue'),
  read('../src/views/warehouse/PurchaseList.vue'),
  read('../src/views/warehouse/InventoryList.vue'),
  read('../src/router/routes.js')
])

assert.match(purchaseCreate, /采购快递单号/)
assert.doesNotMatch(purchaseCreate, /供应商|目标入库仓库|期望到货日期/)
assert.doesNotMatch(receiveDialog, /入库仓库/)
assert.match(receiveDialog, /采购快递单号/)
assert.match(receiveDialog, /未填写采购快递单号/)
assert.match(receiveDialog, /express_no/)
assert.doesNotMatch(purchaseList, /供应商|目标入库仓库|入库仓库/)
assert.doesNotMatch(inventoryList, /getWarehouseOptions|请选择仓库/)
assert.doesNotMatch(routes, /title: '仓库管理'/)

console.log('Single warehouse purchase contract passed')

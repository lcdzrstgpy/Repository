import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')
const [routes, purchaseList, purchaseCreate, inventoryAlerts, purchaseApi] = await Promise.all([
  read('../src/router/routes.js'),
  read('../src/views/warehouse/PurchaseList.vue'),
  read('../src/views/warehouse/PurchaseCreate.vue'),
  read('../src/views/warehouse/InventoryAlerts.vue'),
  read('../src/api/purchase.js')
])

assert.match(routes, /path: 'warehouse\/purchase'[\s\S]*?title: '采购单管理'[\s\S]*?menu: true/)
assert.match(purchaseList, /采购完成/)
assert.doesNotMatch(purchaseList, /@click="handleApprove\(row\)"/)
assert.match(purchaseCreate, /getPurchaseCandidates/)
assert.match(purchaseCreate, /warehouse_id/)
assert.match(purchaseCreate, /suggested_purchase/)
assert.match(inventoryAlerts, /\/warehouse\/purchase\/create/)
assert.match(purchaseApi, /purchase-orders\/candidates/)

console.log('Purchase management flow contract passed')

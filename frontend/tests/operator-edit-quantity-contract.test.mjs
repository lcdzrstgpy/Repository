import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [drawer, api] = await Promise.all([
  readFile(
    new URL('../src/views/operator/components/OrderDetailDrawer.vue', import.meta.url),
    'utf8'
  ),
  readFile(new URL('../src/api/order.js', import.meta.url), 'utf8')
])

assert.match(drawer, /el-input-number[\s\S]*?v-if="detail\.status === 25"/)
assert.match(drawer, /v-model="quantityForm\[row\.id\]"/)
assert.match(drawer, /:min="1"/)
assert.match(drawer, /:precision="0"/)
assert.match(drawer, /confirmQuantity\(detail\.value\.id, \{ items \}\)/)
assert.match(api, /export function confirmQuantity\(orderId, payload\)/)
assert.match(api, /request\.post\(`\/api\/sales-orders\/\$\{orderId\}\/confirm-quantity`, payload\)/)

console.log('Operator editable quantity interaction contract passed')

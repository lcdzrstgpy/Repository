import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(
  new URL('../src/views/warehouse/InventoryList.vue', import.meta.url),
  'utf8'
)

const inboundQuantityInput = source.match(
  /<el-input-number[^>]*v-model="inboundForm\.quantity"[^>]*\/>/
)?.[0]

assert.ok(inboundQuantityInput, '采购入库数量输入框应存在')
assert.match(inboundQuantityInput, /:min="1"/)
assert.match(inboundQuantityInput, /:precision="0"/)
assert.match(inboundQuantityInput, /:step="1"/)
assert.doesNotMatch(inboundQuantityInput, /:precision="2"/)

console.log('Inventory inbound integer quantity contract passed')

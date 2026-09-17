import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(
  new URL('../src/views/warehouse/components/WarehouseOrderDetailDrawer.vue', import.meta.url),
  'utf8'
)

assert.match(source, /const canClaim = computed\(\(\) => detail\.value\?\.status === 10\)/)
assert.match(source, /v-if="canClaim"[\s\S]*?@click="openClaim"/)
assert.match(source, /接单并关联货号/)
assert.match(source, /v-model="claimVisible"/)
assert.match(source, /await getWarehouseOptions\(\)/)
assert.match(source, /await claimOrder\(detail\.value\.id, claimForm\.warehouse_id\)/)
assert.match(source, /await load\(\)[\s\S]*?emit\('updated'\)/)

console.log('WarehouseOrderDetailDrawer claim interaction contract passed')

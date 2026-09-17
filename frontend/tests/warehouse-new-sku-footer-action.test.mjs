import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(
  new URL('../src/views/warehouse/components/WarehouseOrderDetailDrawer.vue', import.meta.url),
  'utf8'
)

assert.match(source, /const pendingNewSkuRow = computed\(/)
assert.match(
  source,
  /<template #footer>[\s\S]*?v-if="pendingNewSkuRow && detail\?\.status === 20"[\s\S]*?@click="openNewSku\(pendingNewSkuRow\)"[\s\S]*?新建货号/
)

console.log('Warehouse new SKU footer action contract passed')

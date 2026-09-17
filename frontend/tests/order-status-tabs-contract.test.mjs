import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const load = (path) => readFile(new URL(path, import.meta.url), 'utf8')
const [operator, warehouse] = await Promise.all([
  load('../src/views/operator/OrderList.vue'),
  load('../src/views/warehouse/PendingOrders.vue')
])

for (const [name, source] of [['operator', operator], ['warehouse', warehouse]]) {
  assert.match(source, /<el-tabs v-model="activeStatusTab"[\s\S]*?@tab-change="handleStatusTabChange"/)
  assert.match(source, /<el-tab-pane label="全部" :name="ALL_STATUS_TAB"/)
  assert.match(source, /v-for="item in ORDER_STATUS_OPTIONS"/)
  assert.doesNotMatch(source, /<el-form-item label="(?:订单)?状态">/)
  assert.match(source, /function handleStatusTabChange\(\) \{\s*query\.page = 1\s*load\(\)/)
  assert.match(source, /const activeStatusTab = computed\(/)
  console.log(`${name} status tabs contract passed`)
}

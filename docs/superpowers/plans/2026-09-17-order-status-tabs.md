# 订单状态标签页实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在运营和仓储的订单列表中，用点击即筛选的订单状态标签页替换状态下拉框。

**Architecture:** 两个 Vue 页面继续使用既有 `query.status` 与既有列表接口。各页面增加一个可写计算属性，把“全部”标签映射为页面既有的空状态值，其余标签映射为数字状态值；标签切换统一将页码重置为 1 后调用既有 `load()`。

**Tech Stack:** Vue 3 `<script setup>`、Element Plus `el-tabs`、Vite、Node.js `assert` 静态交互契约测试。

## Global Constraints

- 复用 `ORDER_STATUS_OPTIONS`，不得重复定义订单状态枚举。
- 不修改后端接口、状态值、角色权限、订单流程或导出接口。
- 保留关键词查询、重置、分页、运营端导出和既有操作按钮。
- 仓储端只有状态 `10` 显示“接单并关联货号”。
- 标签点击必须立即刷新列表并回到第 1 页。

---

### Task 1: 订单状态标签页交互契约

**Files:**
- Create: `frontend/tests/order-status-tabs-contract.test.mjs`
- Modify: `frontend/src/views/operator/OrderList.vue`
- Modify: `frontend/src/views/warehouse/PendingOrders.vue`

**Interfaces:**
- Consumes: `ORDER_STATUS_OPTIONS`，元素结构为 `{ value: number, label: string }`。
- Consumes: 运营端 `query.status` 的全部状态值 `''`，仓储端 `query.status` 的全部状态值 `null`。
- Produces: 两个页面的 `activeStatusTab` 可写计算属性与 `handleStatusTabChange()` 函数。

- [ ] **Step 1: 写入失败的静态交互契约测试**

```js
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `node tests/order-status-tabs-contract.test.mjs`

Expected: `AssertionError`，因为两个页面尚无 `activeStatusTab` 和 `el-tabs`。

- [ ] **Step 3: 以最小实现替换两个状态下拉框**

在两个页面将 Vue 导入更新为：

```js
import { computed, ref, reactive, onMounted } from 'vue'
```

在 `<script setup>` 的查询对象之后添加（运营端的空状态为 `''`）：

```js
const ALL_STATUS_TAB = 'all'
const activeStatusTab = computed({
  get: () => (query.status === '' ? ALL_STATUS_TAB : String(query.status)),
  set: (value) => {
    query.status = value === ALL_STATUS_TAB ? '' : Number(value)
  }
})

function handleStatusTabChange() {
  query.page = 1
  load()
}
```

仓储端使用同样结构，但 `get` 和 `set` 的“全部”状态分别为 `null`：

```js
const ALL_STATUS_TAB = 'all'
const activeStatusTab = computed({
  get: () => (query.status === null ? ALL_STATUS_TAB : String(query.status)),
  set: (value) => {
    query.status = value === ALL_STATUS_TAB ? null : Number(value)
  }
})
```

移除各自查询表单中的状态 `<el-form-item>`，并在表格卡片内工具栏前添加：

```vue
<el-tabs v-model="activeStatusTab" @tab-change="handleStatusTabChange">
  <el-tab-pane label="全部" :name="ALL_STATUS_TAB" />
  <el-tab-pane
    v-for="item in ORDER_STATUS_OPTIONS"
    :key="item.value"
    :label="item.label"
    :name="String(item.value)"
  />
</el-tabs>
```

- [ ] **Step 4: 运行新测试确认通过**

Run: `node tests/order-status-tabs-contract.test.mjs`

Expected: 两个页面各输出一行 `status tabs contract passed`。

- [ ] **Step 5: 运行全量前端验证**

Run: `node tests/order-status-tabs-contract.test.mjs && node tests/admin-partner-page-removed-contract.test.mjs && node tests/operator-edit-quantity-contract.test.mjs && node tests/operator-item-query-contract.test.mjs && node tests/warehouse-order-detail-drawer-claim.test.mjs && npm run build && git diff --check`

Expected: 所有契约测试通过，Vite 生产构建成功，`git diff --check` 无输出。

- [ ] **Step 6: 提交功能改动**

```bash
git add frontend/src/views/operator/OrderList.vue frontend/src/views/warehouse/PendingOrders.vue frontend/tests/order-status-tabs-contract.test.mjs
git commit -m "feat: add order status tabs"
```

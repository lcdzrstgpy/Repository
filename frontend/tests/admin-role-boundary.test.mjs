import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const routes = read('../src/router/routes.js')
const purchaseList = read('../src/views/warehouse/PurchaseList.vue')
const orderDrawer = read('../src/views/operator/components/OrderDetailDrawer.vue')
const dashboard = read('../src/views/Dashboard.vue')

assert.match(routes, /path: 'admin\/orders'/, '管理员需要独立的全部订单入口')
assert.match(routes, /path: 'admin\/purchases'/, '管理员需要独立的采购单入口')
assert.doesNotMatch(routes, /roles: \['operator', 'admin'\]/, '管理员不能进入运营执行页面')
assert.doesNotMatch(routes, /roles: \['warehouse', 'admin'\]/, '管理员不能进入仓储执行页面')
assert.match(routes, /title: '货号管理'[\s\S]*?roles: \['admin'\][\s\S]*?menu: true/, '管理员菜单应提供货号管理')
assert.match(routes, /title: '人员与权限'[\s\S]*?roles: \['admin'\][\s\S]*?menu: true/, '管理员菜单应提供人员与权限')
assert.match(purchaseList, /userStore\.role === 'warehouse'/, '采购执行操作仅仓储可见')
assert.match(orderDrawer, /readonly: \{ type: Boolean, default: false \}/, '订单详情抽屉必须支持只读模式')
assert.match(orderDrawer, /detail\.status === 25 && !readonly/, '只读模式不能填写数量')
assert.match(dashboard, /userStore\.role === 'warehouse'/, '管理员首页不能展示或请求仓储库存预警')

console.log('admin role boundary contract passed')

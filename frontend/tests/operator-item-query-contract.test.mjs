import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [page, api, routes] = await Promise.all([
  readFile(new URL('../src/views/operator/ItemQuery.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/api/basic.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/router/routes.js', import.meta.url), 'utf8')
])

assert.match(api, /export function queryItems\(keyword\)/)
assert.match(api, /request\.get\('\/api\/item-query'/)
assert.match(routes, /path: 'operator\/items'/)
assert.match(routes, /title: '货号查询'/)
assert.match(routes, /roles: \['operator', 'admin'\]/)
assert.match(page, /available_quantity/)
assert.match(page, /库存只读/)

console.log('Operator item inventory query contract passed')

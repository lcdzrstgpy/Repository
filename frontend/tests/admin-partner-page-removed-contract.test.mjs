import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [routes, basicApi] = await Promise.all([
  readFile(new URL('../src/router/routes.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/api/basic.js', import.meta.url), 'utf8')
])

assert.doesNotMatch(routes, /basic\/partners/)
assert.doesNotMatch(routes, /PartnerManage/)
assert.match(basicApi, /export function getPartnerOptions\(type\)/)

console.log('Admin partner page removal contract passed.')

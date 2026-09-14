import type { AuthResponse, Category, CreateSubmissionPayload, Sku, Submission, SubmissionFilters } from '../types'

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()

export const demoCategories: Category[] = [
  { id: 1, categoryName: '家居用品', parentId: null, codePrefix: null, children: [
    { id: 11, categoryName: '杯具', parentId: 1, codePrefix: 'A001' },
    { id: 12, categoryName: '餐具', parentId: 1, codePrefix: 'A002' },
    { id: 13, categoryName: '收纳', parentId: 1, codePrefix: 'A003' },
  ] },
  { id: 2, categoryName: '厨房用品', parentId: null, codePrefix: null, children: [
    { id: 21, categoryName: '锅具', parentId: 2, codePrefix: 'B001' },
    { id: 22, categoryName: '小家电', parentId: 2, codePrefix: 'B002' },
  ] },
  { id: 3, categoryName: '日用百货', parentId: null, codePrefix: null, children: [
    { id: 31, categoryName: '清洁用品', parentId: 3, codePrefix: 'C001' },
    { id: 32, categoryName: '纸品', parentId: 3, codePrefix: 'C002' },
  ] },
  { id: 4, categoryName: '服饰配件', parentId: null, codePrefix: null, children: [
    { id: 41, categoryName: '帽子', parentId: 4, codePrefix: 'D001' },
    { id: 42, categoryName: '围巾', parentId: 4, codePrefix: 'D002' },
  ] },
  { id: 5, categoryName: '宠物用品', parentId: null, codePrefix: null, children: [
    { id: 51, categoryName: '食具', parentId: 5, codePrefix: 'E001' },
    { id: 52, categoryName: '玩具', parentId: 5, codePrefix: 'E002' },
  ] },
  { id: 6, categoryName: '文具', parentId: null, codePrefix: null, children: [
    { id: 61, categoryName: '笔类', parentId: 6, codePrefix: 'F001' },
    { id: 62, categoryName: '本册', parentId: 6, codePrefix: 'F002' },
  ] },
]

export const demoSkus: Sku[] = [
  { id: 101, skuCode: 'A001-12', itemName: '高硼玻璃杯 350ml', categoryId: 11, categoryPath: '家居用品 / 杯具', codeStatus: 'active' },
  { id: 102, skuCode: 'A001-18', itemName: '陶瓷马克杯 白色', categoryId: 11, categoryPath: '家居用品 / 杯具', codeStatus: 'active' },
  { id: 103, skuCode: 'A002-09', itemName: '不锈钢餐勺', categoryId: 12, categoryPath: '家居用品 / 餐具', codeStatus: 'active' },
  { id: 104, skuCode: 'A003-21', itemName: '桌面收纳盒', categoryId: 13, categoryPath: '家居用品 / 收纳', codeStatus: 'active' },
  { id: 105, skuCode: 'E002-07', itemName: '宠物耐咬球', categoryId: 52, categoryPath: '宠物用品 / 玩具', codeStatus: 'active' },
  { id: 106, skuCode: 'F001-16', itemName: '速干中性笔', categoryId: 61, categoryPath: '文具 / 笔类', codeStatus: 'active' },
]

let submissions: Submission[] = [
  {
    id: 1208, submissionNo: 'SUB-20260914-008', status: 2, remark: '欧洲站秋季上新，优先处理。', submittedBy: '林茜', submittedAt: ago(48), statusEnteredAt: ago(18), alert1hAt: null, alert2hAt: null, completedAt: null,
    orders: [
      { id: 2011, orderNo: 'TK-849201-EU', status: 'pending', confirmStatus: 'pending', rejectCount: 1, lines: [
        { id: 3011, lineNo: 1, itemId: 101, skuCode: 'A001-12', itemName: '高硼玻璃杯 350ml', itemDesc: '透明杯，欧规包装', isNewItem: false, categoryId: 11, categoryPath: '家居用品 / 杯具', draftSkuCode: null, qty: null, qtyLockedAt: null, lineStatus: 'pending', rejectReason: null },
        { id: 3012, lineNo: 2, itemId: 107, skuCode: 'D001-24', itemName: '羊毛渔夫帽', itemDesc: '驼色', isNewItem: true, categoryId: 41, categoryPath: '服饰配件 / 帽子', draftSkuCode: 'D001-24', qty: null, qtyLockedAt: null, lineStatus: 'pending', rejectReason: null },
      ] },
      { id: 2012, orderNo: 'TK-849205-EU', status: 'pending', confirmStatus: 'pending', rejectCount: 0, lines: [
        { id: 3013, lineNo: 1, itemId: 105, skuCode: 'E002-07', itemName: '宠物耐咬球', itemDesc: null, isNewItem: false, categoryId: 52, categoryPath: '宠物用品 / 玩具', draftSkuCode: null, qty: null, qtyLockedAt: null, lineStatus: 'pending', rejectReason: null },
      ] },
    ],
    timeline: [
      { key: 'submitted', label: '申请已提交', time: ago(48), done: true },
      { key: 'warehouse', label: '仓库完成货号核验', time: ago(18), done: true },
      { key: 'confirm', label: '等待运营确认货号', time: null, active: true },
      { key: 'quantity', label: '填写并锁定数量', time: null },
      { key: 'fulfil', label: '仓库履约', time: null },
      { key: 'shipped', label: '全部发货', time: null },
    ],
  },
  {
    id: 1207, submissionNo: 'SUB-20260914-007', status: 3, remark: '北美站补单', submittedBy: '林茜', submittedAt: ago(95), statusEnteredAt: ago(72), alert1hAt: ago(10), alert2hAt: null, completedAt: null,
    orders: [
      { id: 2009, orderNo: 'AMZ-US-552871', status: 'pending', confirmStatus: 'confirmed', rejectCount: 0, lines: [
        { id: 3008, lineNo: 1, itemId: 104, skuCode: 'A003-21', itemName: '桌面收纳盒', itemDesc: '米白色', isNewItem: false, categoryId: 13, categoryPath: '家居用品 / 收纳', draftSkuCode: null, qty: null, qtyLockedAt: null, lineStatus: 'confirmed', rejectReason: null },
        { id: 3009, lineNo: 2, itemId: 106, skuCode: 'F001-16', itemName: '速干中性笔', itemDesc: null, isNewItem: false, categoryId: 61, categoryPath: '文具 / 笔类', draftSkuCode: null, qty: null, qtyLockedAt: null, lineStatus: 'confirmed', rejectReason: null },
      ] },
    ],
    timeline: [
      { key: 'submitted', label: '申请已提交', time: ago(95), done: true },
      { key: 'warehouse', label: '仓库完成货号核验', time: ago(77), done: true },
      { key: 'confirm', label: '货号关联已确认', time: ago(72), done: true },
      { key: 'quantity', label: '等待填写发货数量', time: null, active: true },
      { key: 'fulfil', label: '仓库履约', time: null },
      { key: 'shipped', label: '全部发货', time: null },
    ],
  },
  {
    id: 1206, submissionNo: 'SUB-20260914-006', status: 5, remark: null, submittedBy: '林茜', submittedAt: ago(270), statusEnteredAt: ago(190), alert1hAt: ago(210), alert2hAt: ago(150), completedAt: null,
    orders: [
      { id: 2006, orderNo: 'SHP-SG-19372', status: 'shipped', confirmStatus: 'confirmed', rejectCount: 0, shippedAt: ago(40), lines: [{ id: 3004, lineNo: 1, itemId: 103, skuCode: 'A002-09', itemName: '不锈钢餐勺', itemDesc: null, isNewItem: false, categoryId: 12, categoryPath: '家居用品 / 餐具', draftSkuCode: null, qty: 12, qtyLockedAt: ago(200), lineStatus: 'confirmed', rejectReason: null }] },
      { id: 2007, orderNo: 'SHP-SG-19373', status: 'shortage', confirmStatus: 'confirmed', rejectCount: 0, shortageAt: ago(80), lines: [{ id: 3005, lineNo: 1, itemId: 102, skuCode: 'A001-18', itemName: '陶瓷马克杯 白色', itemDesc: null, isNewItem: false, categoryId: 11, categoryPath: '家居用品 / 杯具', draftSkuCode: null, qty: 24, qtyLockedAt: ago(200), lineStatus: 'confirmed', rejectReason: null }] },
      { id: 2008, orderNo: 'SHP-SG-19374', status: 'ordered', confirmStatus: 'confirmed', rejectCount: 0, lines: [{ id: 3006, lineNo: 1, itemId: 105, skuCode: 'E002-07', itemName: '宠物耐咬球', itemDesc: null, isNewItem: false, categoryId: 52, categoryPath: '宠物用品 / 玩具', draftSkuCode: null, qty: 8, qtyLockedAt: ago(200), lineStatus: 'confirmed', rejectReason: null }] },
    ],
    timeline: [
      { key: 'submitted', label: '申请已提交', time: ago(270), done: true },
      { key: 'warehouse', label: '仓库完成货号核验', time: ago(245), done: true },
      { key: 'confirm', label: '货号关联已确认', time: ago(230), done: true },
      { key: 'quantity', label: '数量已锁定', time: ago(200), done: true },
      { key: 'fulfil', label: '仓库作业中', time: ago(190), active: true, detail: '1 个订单缺货待补货' },
      { key: 'shipped', label: '全部发货', time: null },
    ],
  },
  {
    id: 1205, submissionNo: 'SUB-20260914-005', status: 1, remark: '新品样单', submittedBy: '林茜', submittedAt: ago(155), statusEnteredAt: ago(155), alert1hAt: ago(90), alert2hAt: ago(30), completedAt: null,
    orders: [{ id: 2005, orderNo: 'SAMPLE-0914-05', status: 'pending', confirmStatus: 'pending', rejectCount: 0, lines: [{ id: 3003, lineNo: 1, itemId: null, skuCode: null, itemName: null, itemDesc: '可折叠硅胶饭盒', isNewItem: true, categoryId: 12, categoryPath: '家居用品 / 餐具', draftSkuCode: null, qty: null, qtyLockedAt: null, lineStatus: 'pending', rejectReason: null }] }],
    timeline: [{ key: 'submitted', label: '申请已提交', time: ago(155), done: true }, { key: 'warehouse', label: '等待仓库核验', time: null, active: true }, { key: 'confirm', label: '确认货号', time: null }, { key: 'quantity', label: '填写数量', time: null }, { key: 'fulfil', label: '仓库履约', time: null }, { key: 'shipped', label: '全部发货', time: null }],
  },
]

const copy = <T>(value: T): T => structuredClone(value)

export const demoApi = {
  login(username: string, password: string): AuthResponse {
    if (!username || !password) throw new Error('请输入账号和密码')
    return { accessToken: 'demo-operator-token', expiresIn: 28800, user: { id: 'op-01', username, displayName: '林茜', role: 'operator' } }
  },
  searchSkus(query: string) {
    const keyword = query.trim().toLowerCase()
    return copy(demoSkus.filter((sku) => !keyword || `${sku.skuCode}${sku.itemName}`.toLowerCase().includes(keyword)).slice(0, 8))
  },
  categories() { return copy(demoCategories) },
  list(filters: SubmissionFilters) {
    let result = submissions
    if (filters.status) result = result.filter((item) => String(item.status) === filters.status)
    if (filters.orderNo) result = result.filter((item) => item.orders.some((order) => order.orderNo.toLowerCase().includes(filters.orderNo!.toLowerCase())))
    if (filters.shortageOnly) result = result.filter((item) => item.orders.some((order) => order.status === 'shortage'))
    return copy([...result].sort((a, b) => {
      const actionA = a.status === 2 || a.status === 3 ? 1 : 0
      const actionB = b.status === 2 || b.status === 3 ? 1 : 0
      return actionB - actionA || +new Date(b.submittedAt) - +new Date(a.submittedAt)
    }))
  },
  detail(id: number) {
    const found = submissions.find((item) => item.id === id)
    if (!found) throw new Error('申请不存在')
    return copy(found)
  },
  create(payload: CreateSubmissionPayload) {
    const id = Math.max(...submissions.map((item) => item.id)) + 1
    const now = new Date().toISOString()
    const next: Submission = {
      id, submissionNo: `SUB-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${String(id).slice(-3)}`, status: 1, remark: payload.remark ?? null, submittedBy: '林茜', submittedAt: now, statusEnteredAt: now, alert1hAt: null, alert2hAt: null, completedAt: null,
      orders: payload.orders.map((order, orderIndex) => ({ id: id * 10 + orderIndex, orderNo: order.orderNo, status: 'pending', confirmStatus: 'pending', rejectCount: 0, lines: order.lines.map((line, lineIndex) => { const sku = demoSkus.find((item) => item.id === line.itemId); const category = demoCategories.flatMap((item) => item.children ?? []).find((item) => item.id === line.categoryId); return { id: id * 100 + orderIndex * 10 + lineIndex, lineNo: lineIndex + 1, itemId: line.itemId, skuCode: sku?.skuCode ?? null, itemName: sku?.itemName ?? null, itemDesc: line.itemDesc ?? null, isNewItem: line.isNewItem, categoryId: line.categoryId, categoryPath: category ? `${demoCategories.find((item) => item.id === category.parentId)?.categoryName} / ${category.categoryName}` : null, draftSkuCode: null, qty: null, qtyLockedAt: null, lineStatus: 'pending', rejectReason: null } }) })),
      timeline: [{ key: 'submitted', label: '申请已提交', time: now, done: true }, { key: 'warehouse', label: '等待仓库核验', time: null, active: true }, { key: 'confirm', label: '确认货号', time: null }, { key: 'quantity', label: '填写数量', time: null }, { key: 'fulfil', label: '仓库履约', time: null }, { key: 'shipped', label: '全部发货', time: null }],
    }
    submissions = [next, ...submissions]
    return copy(next)
  },
  confirmSkus(id: number) {
    const item = submissions.find((submission) => submission.id === id)
    if (!item) throw new Error('申请不存在')
    item.orders.forEach((order) => { if (order.confirmStatus === 'pending') order.confirmStatus = 'confirmed' })
    item.status = 3
    item.statusEnteredAt = new Date().toISOString()
    return copy(item)
  },
  rejectOrder(id: number, orderId: number, reason: string) {
    const item = submissions.find((submission) => submission.id === id)
    const order = item?.orders.find((candidate) => candidate.id === orderId)
    if (!item || !order) throw new Error('订单不存在')
    if (order.rejectCount >= 3) throw new Error('该订单已达到驳回上限')
    order.confirmStatus = 'rejected'; order.rejectCount += 1; item.status = 1; item.statusEnteredAt = new Date().toISOString()
    order.lines.forEach((line) => { line.lineStatus = 'rejected'; line.rejectReason = reason })
    return copy(item)
  },
  lockQuantities(id: number, quantities: Array<{ lineId: number; qty: number }>) {
    const item = submissions.find((submission) => submission.id === id)
    if (!item) throw new Error('申请不存在')
    const now = new Date().toISOString()
    item.orders.flatMap((order) => order.lines).forEach((line) => { const input = quantities.find((value) => value.lineId === line.id); if (input) { line.qty = input.qty; line.qtyLockedAt = now } })
    item.status = 4; item.statusEnteredAt = now
    return copy(item)
  },
  cancel(id: number) {
    const item = submissions.find((submission) => submission.id === id)
    if (!item) throw new Error('申请不存在')
    item.status = 'CANCELLED'; item.orders.forEach((order) => { order.status = 'cancelled' })
    return copy(item)
  },
}

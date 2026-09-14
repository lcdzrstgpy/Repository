import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { SkuSearch } from '../components/SkuSearch'
import type { Category, DraftLine, DraftOrder, Sku } from '../types'
import { createIdempotencyKey, createKey } from '../utils/format'

const blankLine = (): DraftLine => ({ key: createKey(), itemId: null, skuCode: '', itemDesc: '', isNewItem: false, categoryId: null })
const blankOrder = (): DraftOrder => ({ key: createKey(), orderNo: '', lines: [blankLine()] })

export function SubmitPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<DraftOrder[]>([blankOrder()])
  const [remark, setRemark] = useState('')
  const [categories, setCategories] = useState<Category[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const totalLines = useMemo(() => orders.reduce((sum, order) => sum + order.lines.length, 0), [orders])
  useEffect(() => { api.catalog.categories().then(setCategories).catch(() => setCategories([])) }, [])

  const updateOrder = (orderKey: string, updater: (order: DraftOrder) => DraftOrder) => setOrders((current) => current.map((order) => order.key === orderKey ? updater(order) : order))
  const updateLine = (orderKey: string, lineKey: string, patch: Partial<DraftLine>) => updateOrder(orderKey, (order) => ({ ...order, lines: order.lines.map((line) => line.key === lineKey ? { ...line, ...patch } : line) }))
  const chooseSku = (orderKey: string, line: DraftLine, sku: Sku | null, input: string) => updateLine(orderKey, line.key, { itemId: sku?.id ?? null, skuCode: input, itemDesc: sku ? sku.itemName : line.itemDesc, categoryId: sku?.categoryId ?? line.categoryId })

  const validate = () => {
    const next: Record<string, string> = {}
    const seen = new Set<string>()
    orders.forEach((order) => {
      const orderNo = order.orderNo.trim()
      if (!orderNo) next[`order-${order.key}`] = '请输入订单号'
      else if (orderNo.length > 128) next[`order-${order.key}`] = '订单号不能超过 128 个字符'
      else if (seen.has(orderNo)) next[`order-${order.key}`] = '同一批次内订单号不可重复'
      seen.add(orderNo)
      order.lines.forEach((line) => {
        if (line.isNewItem && !line.categoryId) next[`line-${line.key}`] = '新品必须选择二级类目'
        if (!line.isNewItem && !line.itemId) next[`line-${line.key}`] = '请从检索结果中选择有效货号'
        if (line.itemDesc.length > 255) next[`desc-${line.key}`] = '商品描述不能超过 255 个字符'
      })
    })
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async () => {
    if (!validate()) return
    setSubmitting(true)
    try {
      const idempotencyKey = await createIdempotencyKey(orders.map((order) => order.orderNo.trim()))
      const created = await api.submissions.create({
        idempotencyKey,
        remark: remark.trim() || undefined,
        orders: orders.map((order) => ({ orderNo: order.orderNo.trim(), lines: order.lines.map((line) => ({ itemId: line.isNewItem ? null : line.itemId, itemDesc: line.itemDesc.trim() || undefined, isNewItem: line.isNewItem, categoryId: line.isNewItem ? line.categoryId : null })) })),
      })
      navigate(`/requests/${created.id}`, { state: { created: true } })
    } catch (reason) { setErrors({ form: reason instanceof Error ? reason.message : '提交失败，请重试' }) }
    finally { setSubmitting(false) }
  }

  return <div className="submit-page">
    <section className="workflow-strip"><div className="workflow-copy"><span className="eyebrow">NEW SUBMISSION</span><h2>创建发货申请批次</h2><p>先提交订单与商品信息，货号确认后再填写发货数量。</p></div><div className="workflow-steps"><div className="active"><span>01</span><strong>提交订单</strong></div><i/><div><span>02</span><strong>确认货号</strong></div><i/><div><span>03</span><strong>锁定数量</strong></div></div></section>
    {errors.form && <div className="form-error page-error"><Icon name="alert" />{errors.form}</div>}
    <div className="form-layout">
      <div className="orders-column">
        {orders.map((order, orderIndex) => <section className="order-card" key={order.key}>
          <header className="order-card-head"><div className="order-index">{String(orderIndex + 1).padStart(2, '0')}</div><div className="order-title"><span>订单号</span><input className={errors[`order-${order.key}`] ? 'invalid' : ''} value={order.orderNo} maxLength={129} onChange={(event) => updateOrder(order.key, (value) => ({ ...value, orderNo: event.target.value }))} placeholder="例如 TK-849201-EU" />{errors[`order-${order.key}`] && <small className="field-error">{errors[`order-${order.key}`]}</small>}</div>{orders.length > 1 && <button className="text-button danger" type="button" onClick={() => setOrders((current) => current.filter((value) => value.key !== order.key))}><Icon name="trash" size={15}/>删除订单</button>}</header>
          <div className="line-table">
            <div className="line-table-head"><span>行</span><span>货号检索</span><span>商品名称 / 描述</span><span>新品申请</span><span>二级类目</span><span /></div>
            {order.lines.map((line, lineIndex) => <div className={`line-row ${errors[`line-${line.key}`] ? 'has-error' : ''}`} key={line.key}>
              <span className="line-number">{String(lineIndex + 1).padStart(2, '0')}</span>
              <div><SkuSearch value={line.skuCode} disabled={line.isNewItem} onSelect={(sku, input) => chooseSku(order.key, line, sku, input)} />{errors[`line-${line.key}`] && <small className="field-error">{errors[`line-${line.key}`]}</small>}</div>
              <div><input className={errors[`desc-${line.key}`] ? 'invalid' : ''} value={line.itemDesc} maxLength={256} onChange={(event) => updateLine(order.key, line.key, { itemDesc: event.target.value })} placeholder="可留空，选中货号后自动带出" />{errors[`desc-${line.key}`] && <small className="field-error">{errors[`desc-${line.key}`]}</small>}</div>
              <label className="switch-field"><input type="checkbox" checked={line.isNewItem} onChange={(event) => updateLine(order.key, line.key, { isNewItem: event.target.checked, itemId: null, skuCode: '', categoryId: event.target.checked ? line.categoryId : null })}/><span className="switch"/><em>{line.isNewItem ? '新品' : '老品'}</em></label>
              <select value={line.categoryId ?? ''} disabled={!line.isNewItem} onChange={(event) => updateLine(order.key, line.key, { categoryId: Number(event.target.value) || null })}><option value="">选择二级类目</option>{categories.map((parent) => <optgroup label={parent.categoryName} key={parent.id}>{parent.children?.map((child) => <option value={child.id} key={child.id}>{child.categoryName} · {child.codePrefix}</option>)}</optgroup>)}</select>
              <button className="icon-button row-delete" type="button" disabled={order.lines.length === 1} onClick={() => updateOrder(order.key, (value) => ({ ...value, lines: value.lines.filter((item) => item.key !== line.key) }))} aria-label="删除行"><Icon name="trash" size={16}/></button>
            </div>)}
          </div>
          <button className="add-line" type="button" onClick={() => updateOrder(order.key, (value) => ({ ...value, lines: [...value.lines, blankLine()] }))}><Icon name="plus" size={15}/> 添加商品行</button>
        </section>)}
        <button className="add-order" type="button" onClick={() => setOrders((current) => [...current, blankOrder()])}><span><Icon name="plus"/></span><div><strong>新增订单号</strong><small>同一批次可包含多个独立发货订单</small></div></button>
      </div>
      <aside className="submit-summary">
        <div className="summary-head"><Icon name="file"/><div><h3>批次摘要</h3><span>提交后生成唯一批次号</span></div></div>
        <div className="summary-stats"><div><strong>{orders.length}</strong><span>订单数</span></div><div><strong>{totalLines}</strong><span>商品行</span></div></div>
        <label>批次备注 <span>可选</span><textarea value={remark} maxLength={1000} onChange={(event) => setRemark(event.target.value)} placeholder="说明整批采购内容或需要仓库留意的事项…"/><small>{remark.length} / 1000</small></label>
        <div className="info-note"><Icon name="alert" size={17}/><p><strong>此阶段无需填写数量</strong>仓库完成货号核验后，系统将通知你进行确认。</p></div>
        <button className="button button-primary submit-button" onClick={submit} disabled={submitting}>{submitting ? '正在提交…' : '提交整个批次'}<Icon name="arrow"/></button>
        <p className="safe-note">已启用幂等保护，重复点击不会生成重复批次</p>
      </aside>
    </div>
  </div>
}

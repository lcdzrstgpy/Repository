import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { Modal } from '../components/Modal'
import { ConfirmBadge } from '../components/StatusBadge'
import { useSubmissionStore } from '../store/submissions'
import type { SubmissionOrder } from '../types'

export function ConfirmPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { current, loading, loadOne } = useSubmissionStore()
  const [rejectOrder, setRejectOrder] = useState<SubmissionOrder | null>(null)
  const [reason, setReason] = useState('')
  const [quantities, setQuantities] = useState<Record<number, string>>({})
  const [confirmLock, setConfirmLock] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  useEffect(() => { if (id) void loadOne(Number(id)) }, [id, loadOne])
  useEffect(() => {
    if (current && current.status === 3) {
      const values: Record<number, string> = {}
      current.orders.forEach((order) => order.lines.forEach((line) => { values[line.id] = line.qty ? String(line.qty) : '' }))
      setQuantities(values)
    }
  }, [current])
  const rejectedCount = useMemo(() => current?.orders.filter((order) => order.confirmStatus === 'rejected').length ?? 0, [current])
  if (loading && !current) return <div className="loading-state page-loading">正在加载确认内容…</div>
  if (!current || current.id !== Number(id)) return <div className="empty-state"><strong>未找到该申请</strong><button className="button button-secondary" onClick={() => navigate('/requests')}>返回申请列表</button></div>

  const confirmSkus = async () => {
    setSubmitting(true); setError('')
    try { await api.submissions.confirmSkus(current.id); await loadOne(current.id) }
    catch (reasonValue) { setError(reasonValue instanceof Error ? reasonValue.message : '确认失败') }
    finally { setSubmitting(false) }
  }
  const reject = async () => {
    if (!rejectOrder || !reason.trim()) return setError('请填写驳回原因')
    setSubmitting(true)
    try { await api.submissions.rejectOrder(current.id, rejectOrder.id, reason.trim()); navigate(`/requests/${current.id}`, { replace: true }) }
    catch (reasonValue) { setError(reasonValue instanceof Error ? reasonValue.message : '驳回失败') }
    finally { setSubmitting(false) }
  }
  const requestLock = () => {
    const invalid = current.orders.flatMap((order) => order.lines).find((line) => !Number.isInteger(Number(quantities[line.id])) || Number(quantities[line.id]) < 1)
    if (invalid) return setError(`订单明细第 ${invalid.lineNo} 行的数量必须是大于等于 1 的整数`)
    setError(''); setConfirmLock(true)
  }
  const lock = async () => {
    setSubmitting(true)
    try {
      const lines = current.orders.flatMap((order) => order.lines).map((line) => ({ lineId: line.id, qty: Number(quantities[line.id]) }))
      await api.submissions.lockQuantities(current.id, lines)
      navigate(`/requests/${current.id}`, { replace: true, state: { locked: true } })
    } catch (reasonValue) { setError(reasonValue instanceof Error ? reasonValue.message : '数量提交失败'); setConfirmLock(false) }
    finally { setSubmitting(false) }
  }
  const stage = current.status === 2 ? 'sku' : current.status === 3 ? 'qty' : 'locked'

  return <div className="confirm-page">
    <button className="back-link" onClick={() => navigate(`/requests/${current.id}`)}><Icon name="chevron" size={16}/> 返回申请详情</button>
    <section className="confirm-header"><div><span className="eyebrow">{current.submissionNo}</span><h2>{stage === 'sku' ? '确认货号关联' : stage === 'qty' ? '填写发货数量' : '本批次已进入后续流程'}</h2><p>{stage === 'sku' ? '逐订单核对仓库确认的货号；确认是整批操作，驳回按订单操作。' : stage === 'qty' ? '逐行填写本次实际发货数量，提交后将永久锁定。' : '当前状态不允许运营继续修改。'}</p></div><div className="stage-indicator"><span className={stage === 'sku' ? 'active' : 'done'}><i>{stage === 'sku' ? '1' : <Icon name="check" size={13}/>}</i>货号确认</span><b/><span className={stage === 'qty' ? 'active' : stage === 'locked' ? 'done' : ''}><i>{stage === 'locked' ? <Icon name="check" size={13}/> : '2'}</i>数量确认</span></div></section>
    {error && <div className="form-error page-error"><Icon name="alert"/>{error}</div>}
    <div className="confirm-orders">{current.orders.map((order, orderIndex) => <section className="confirm-order" key={order.id}>
      <header><div className="order-index">{String(orderIndex + 1).padStart(2, '0')}</div><div><span>订单号</span><strong>{order.orderNo}</strong></div><ConfirmBadge status={order.confirmStatus}/><span className="reject-count">已驳回 {order.rejectCount}/3</span>{stage === 'sku' && <button className="button button-small button-danger-outline" disabled={order.rejectCount >= 3 || order.confirmStatus === 'rejected'} onClick={() => { setRejectOrder(order); setReason(''); setError('') }}>{order.rejectCount >= 3 ? '已达驳回上限' : '驳回此订单'}</button>}</header>
      <div className={`confirmation-table stage-${stage}`}><div className="confirmation-head"><span>行</span><span>货号</span><span>商品名称 / 描述</span><span>二级类目</span><span>{stage === 'qty' ? '发货数量' : '数量'}</span></div>
        {order.lines.map((line) => <div className="confirmation-row" key={line.id}><span className="line-number">{String(line.lineNo).padStart(2, '0')}</span><div><strong>{line.skuCode ?? line.draftSkuCode ?? '待生成'}</strong>{line.isNewItem && <span className="new-tag">新品</span>}</div><div><strong>{line.itemName ?? line.itemDesc ?? '—'}</strong>{line.itemDesc && line.itemName !== line.itemDesc && <small>{line.itemDesc}</small>}</div><span>{line.categoryPath ?? '—'}</span>{stage === 'qty' ? <div className="quantity-input"><input inputMode="numeric" min="1" step="1" value={quantities[line.id] ?? ''} onChange={(event) => setQuantities((value) => ({ ...value, [line.id]: event.target.value.replace(/[^0-9]/g, '') }))}/><small>件</small></div> : <span className="qty-placeholder">待第二次确认时填写</span>}</div>)}
      </div>
      {order.rejectCount >= 3 && stage === 'sku' && <div className="limit-note"><Icon name="alert" size={15}/>该订单已达到 3 次驳回上限，如仍有问题请联系仓库管理员。</div>}
    </section>)}</div>
    <footer className="confirm-footer"><div className={`lock-warning ${stage === 'qty' ? 'important' : ''}`}><Icon name={stage === 'qty' ? 'alert' : 'check'}/><div><strong>{stage === 'qty' ? '请在提交前仔细核对数量' : stage === 'sku' ? '货号确认后将进入数量确认' : '运营操作已锁定'}</strong><span>{stage === 'qty' ? '提交后数量将锁定，且本批次不能再由你修改或取消。' : stage === 'sku' ? '整批确认后，所有货号关联将不可再由仓库修改。' : '如需变更，请联系仓库管理员处理。'}</span></div></div>
      {stage === 'sku' && <button className="button button-primary large" disabled={submitting || rejectedCount > 0} onClick={confirmSkus}>{rejectedCount > 0 ? `还有 ${rejectedCount} 个订单在处理中` : submitting ? '正在确认…' : '确认整批货号关联'}<Icon name="arrow"/></button>}
      {stage === 'qty' && <button className="button button-primary large" disabled={submitting} onClick={requestLock}>提交并锁定数量 <Icon name="check"/></button>}
      {stage === 'locked' && <button className="button button-secondary large" onClick={() => navigate(`/requests/${current.id}`)}>查看最新进度</button>}
    </footer>
    {rejectOrder && <Modal title={`驳回订单 ${rejectOrder.orderNo}`} onClose={() => setRejectOrder(null)} footer={<><button className="button button-ghost" onClick={() => setRejectOrder(null)}>返回核对</button><button className="button button-danger" disabled={submitting} onClick={reject}>确认驳回</button></>}><div className="modal-warning"><Icon name="alert"/><p>仅此订单会退回仓库修改，其他已确认订单保持原状态。批次将回到状态 ①。</p></div><label>驳回原因 <b>*</b><textarea autoFocus value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} placeholder="请具体说明货号或商品信息的问题"/><small>{reason.length} / 500</small></label>{error && <small className="field-error">{error}</small>}</Modal>}
    {confirmLock && <Modal title="确认锁定发货数量" onClose={() => setConfirmLock(false)} footer={<><button className="button button-ghost" onClick={() => setConfirmLock(false)}>再检查一下</button><button className="button button-primary" disabled={submitting} onClick={lock}>{submitting ? '正在锁定…' : '确认提交并锁定'}</button></>}><div className="modal-warning serious"><Icon name="alert"/><p><strong>此操作不可撤销</strong>数量锁定后，运营不能再修改货号、数量或取消本批次。后续变更需联系仓库管理员。</p></div><div className="lock-summary"><span>订单数<strong>{current.orders.length}</strong></span><span>商品行<strong>{current.orders.reduce((sum, order) => sum + order.lines.length, 0)}</strong></span><span>总件数<strong>{Object.values(quantities).reduce((sum, qty) => sum + Number(qty || 0), 0)}</strong></span></div></Modal>}
  </div>
}

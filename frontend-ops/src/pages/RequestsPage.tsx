import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { Modal } from '../components/Modal'
import { StatusBadge } from '../components/StatusBadge'
import { SubmissionDetail } from '../components/SubmissionDetail'
import { useSubmissionStore } from '../store/submissions'
import type { Submission, SubmissionFilters } from '../types'
import { formatDate, orderProgress, timeoutLevel, timeoutText } from '../utils/format'

export function RequestsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { submissions, current, loading, error, setFilters, load, loadOne } = useSubmissionStore()
  const [draftFilters, setDraftFilters] = useState<SubmissionFilters>({})
  const [cancelTarget, setCancelTarget] = useState<Submission | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [actionError, setActionError] = useState('')
  const [createdNotice, setCreatedNotice] = useState(Boolean((location.state as { created?: boolean } | null)?.created))

  useEffect(() => { setFilters({}); void load() }, [load, setFilters])
  useEffect(() => { if (id) void loadOne(Number(id)) }, [id, loadOne])

  const applyFilters = () => { setFilters(draftFilters); void load() }
  const select = (submission: Submission) => navigate(`/requests/${submission.id}`)
  const cancel = async () => {
    if (!cancelTarget || !cancelReason.trim()) return setActionError('请填写取消原因')
    try { await api.submissions.cancel(cancelTarget.id, cancelReason.trim()); setCancelTarget(null); setCancelReason(''); setActionError(''); await load(); if (id === String(cancelTarget.id)) await loadOne(cancelTarget.id) }
    catch (reason) { setActionError(reason instanceof Error ? reason.message : '取消失败') }
  }

  return <div className={`requests-page ${id ? 'with-detail' : ''}`}>
    <div className="request-master">
      {createdNotice && <div className="success-banner"><Icon name="check"/><div><strong>批次提交成功</strong><span>仓库将开始核验货号，你可以在这里持续跟踪进度。</span></div><button className="icon-button" onClick={() => setCreatedNotice(false)}><Icon name="x"/></button></div>}
      <section className="filter-card">
        <div className="filter-main"><div className="filter-search"><Icon name="search" size={17}/><input placeholder="搜索订单号" value={draftFilters.orderNo ?? ''} onChange={(event) => setDraftFilters((value) => ({ ...value, orderNo: event.target.value }))} onKeyDown={(event) => { if (event.key === 'Enter') applyFilters() }}/></div>
          <select value={draftFilters.status ?? ''} onChange={(event) => setDraftFilters((value) => ({ ...value, status: event.target.value }))}><option value="">全部状态</option><option value="1">待仓库处理</option><option value="2">待确认货号</option><option value="3">待填写数量</option><option value="4">待作业</option><option value="5">作业中</option><option value="6">已发货</option><option value="CANCELLED">已取消</option></select>
          <input type="date" aria-label="开始日期" value={draftFilters.from ?? ''} onChange={(event) => setDraftFilters((value) => ({ ...value, from: event.target.value }))}/><span className="date-separator">—</span><input type="date" aria-label="结束日期" value={draftFilters.to ?? ''} onChange={(event) => setDraftFilters((value) => ({ ...value, to: event.target.value }))}/>
          <label className="checkbox-filter"><input type="checkbox" checked={draftFilters.shortageOnly ?? false} onChange={(event) => setDraftFilters((value) => ({ ...value, shortageOnly: event.target.checked }))}/>仅看缺货</label>
          <button className="button button-secondary" onClick={applyFilters}>筛选</button>
        </div>
        <div className="filter-meta"><span>共 {submissions.length} 个批次</span><span><i className="sort-dot"/>待我处理优先，其次按提交时间倒序</span></div>
      </section>
      {error && <div className="form-error page-error"><Icon name="alert"/>{error}</div>}
      <section className="requests-table-card">
        <div className="requests-table-head"><span>提交单 / 订单号</span><span>提交时间</span><span>当前状态</span><span>订单进度</span><span>响应时效</span><span>操作</span></div>
        <div className="requests-list">{loading && !submissions.length ? <div className="loading-state">正在加载申请…</div> : submissions.map((submission) => {
          const progress = orderProgress(submission); const timeout = timeoutLevel(submission); const actionable = submission.status === 2 || submission.status === 3
          return <article className={`request-row ${Number(id) === submission.id ? 'selected' : ''} ${timeout === 2 ? 'overdue' : ''}`} key={submission.id} onClick={() => select(submission)}>
            <div className="submission-cell"><strong>{submission.submissionNo}</strong><span>{submission.orders.length === 1 ? submission.orders[0].orderNo : `${submission.orders[0].orderNo} 等 ${submission.orders.length} 个`}</span></div>
            <time>{formatDate(submission.submittedAt)}</time>
            <div><StatusBadge status={submission.status}/>{actionable && <small className="action-needed">需要你处理</small>}</div>
            <div className="progress-cell"><strong>{progress.shipped}/{progress.total} 已发货</strong>{progress.shortage > 0 && <span className="shortage"><Icon name="alert" size={13}/>{progress.shortage} 个缺货</span>}<div className="progress-bar"><i style={{ width: `${progress.total ? progress.shipped / progress.total * 100 : 0}%` }}/></div></div>
            <div className={`timeout-cell level-${timeout}`}><Icon name="clock" size={15}/><span>{timeoutText(submission)}</span></div>
            <div className="row-actions" onClick={(event) => event.stopPropagation()}>{actionable ? <button className="button button-small button-primary" onClick={() => navigate(`/confirm/${submission.id}`)}>去确认</button> : <button className="button button-small button-ghost" onClick={() => select(submission)}>详情</button>}{typeof submission.status === 'number' && submission.status <= 3 && <button className="more-button" title="取消申请" onClick={() => setCancelTarget(submission)}>取消</button>}</div>
          </article>
        })}{!loading && !submissions.length && <div className="empty-state"><Icon name="file" size={30}/><strong>没有匹配的申请</strong><span>调整筛选条件后重试</span></div>}</div>
      </section>
    </div>
    {id && <aside className="request-detail-wrap"><button className="detail-close icon-button" onClick={() => navigate('/requests')}><Icon name="x"/></button>{current?.id === Number(id) ? <SubmissionDetail submission={current} onConfirm={() => navigate(`/confirm/${current.id}`)}/> : <div className="loading-state">加载详情…</div>}</aside>}
    {cancelTarget && <Modal title={`取消 ${cancelTarget.submissionNo}`} onClose={() => { setCancelTarget(null); setActionError('') }} footer={<><button className="button button-ghost" onClick={() => setCancelTarget(null)}>返回</button><button className="button button-danger" onClick={cancel}>确认取消</button></>}><p className="modal-note">取消后不可恢复。运营仅可取消状态 ①–③ 的批次。</p><label>取消原因 <b>*</b><textarea autoFocus value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="请填写取消原因"/></label>{actionError && <small className="field-error">{actionError}</small>}</Modal>}
  </div>
}

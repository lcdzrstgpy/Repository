import type { Submission } from '../types'
import { formatDate, orderProgress, timeoutLevel, timeoutText } from '../utils/format'
import { ConfirmBadge, OrderStatusBadge, StatusBadge } from './StatusBadge'
import { Icon } from './Icon'

export function SubmissionDetail({ submission, onConfirm }: { submission: Submission; onConfirm: () => void }) {
  const progress = orderProgress(submission)
  const timeout = timeoutLevel(submission)
  return <div className="detail-panel">
    <div className="detail-head">
      <div><span className="eyebrow">提交单详情</span><h2>{submission.submissionNo}</h2></div>
      <StatusBadge status={submission.status} />
    </div>
    {timeout > 0 && <div className={`timeout-banner level-${timeout}`}><Icon name="clock"/><div><strong>{timeout === 2 ? '处理已严重超时' : '即将超出响应目标'}</strong><span>{timeoutText(submission)}，请尽快跟进当前责任方</span></div></div>}
    <div className="metrics-grid">
      <div><span>提交时间</span><strong>{formatDate(submission.submittedAt)}</strong></div>
      <div><span>订单进度</span><strong>{progress.shipped} / {progress.total} 已发货</strong></div>
      <div><span>缺货订单</span><strong className={progress.shortage ? 'danger-text' : ''}>{progress.shortage} 个</strong></div>
    </div>
    <section className="detail-section"><div className="section-heading"><h3>进度节点</h3><span>状态自动回传</span></div><div className="timeline">
      {submission.timeline.map((event) => <div className={`timeline-item ${event.done ? 'done' : ''} ${event.active ? 'active' : ''}`} key={event.key}><span className="timeline-dot">{event.done ? <Icon name="check" size={13}/> : ''}</span><div><strong>{event.label}</strong>{event.detail && <small>{event.detail}</small>}</div><time>{formatDate(event.time)}</time></div>)}
    </div></section>
    <section className="detail-section"><div className="section-heading"><h3>订单明细</h3><span>{submission.orders.length} 个订单</span></div>
      <div className="detail-orders">{submission.orders.map((order) => <details key={order.id} open><summary><div><strong>{order.orderNo}</strong><small>{order.lines.length} 行商品 · 驳回 {order.rejectCount}/3</small></div><div><ConfirmBadge status={order.confirmStatus}/><OrderStatusBadge status={order.status}/></div></summary>
        <div className="detail-lines">{order.lines.map((line) => <div className="detail-line" key={line.id}><span className="line-number">{String(line.lineNo).padStart(2, '0')}</span><div><strong>{line.skuCode ?? '待生成货号'}</strong><small>{line.itemName ?? line.itemDesc ?? '未填写描述'}</small></div><div><small>类目</small><span>{line.categoryPath ?? '—'}</span></div><div><small>数量</small><span>{line.qty ?? '待确认'}</span></div>{line.isNewItem && <span className="new-tag">新品</span>}</div>)}</div>
      </details>)}</div>
    </section>
    {submission.remark && <section className="detail-section remark"><h3>批次备注</h3><p>{submission.remark}</p></section>}
    {(submission.status === 2 || submission.status === 3) && <div className="sticky-action"><button className="button button-primary" onClick={onConfirm}>去处理当前确认 <Icon name="arrow"/></button></div>}
  </div>
}

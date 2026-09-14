import { useEffect, useState } from 'react';
import { api } from '../api.js';
import DataTable from '../components/DataTable.jsx';
import PageHeader from '../components/PageHeader.jsx';
import Modal from '../components/Modal.jsx';
import HubSkuPicker from '../components/HubSkuPicker.jsx';

// Hub 提交单的仓库端处理台。数据经由 wms 后端的 /api/admin/hub/* 代理
// 转发到中枢（见 api/routes/admin/admin_hub.py），所以这里不需要、也拿不到
// 中枢的共享密钥。
//
// 状态 ① 的批次要在这里核验：新品行必须给出正式商品名（核验时才生成
// 待审核货号）；被运营驳回的批次则走 rework 回到待确认。

const STATUS_OPTIONS = [
  { label: '待仓库处理（①）', value: '1' },
  { label: '待运营确认货号（②）', value: '2' },
  { label: '全部', value: '' },
];

const CONFIRM_LABEL = { pending: '待确认', confirmed: '已确认', rejected: '已驳回' };

function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('zh-CN', { hour12: false });
}

function orderSummary(orders) {
  if (!orders || orders.length === 0) return '—';
  return orders.length === 1 ? orders[0].order_no : `${orders[0].order_no} 等 ${orders.length} 个`;
}

function allLines(submission) {
  return submission ? submission.orders.flatMap((order) => order.lines) : [];
}

async function readError(res, fallback) {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (data?.detail?.message) return data.detail.message;
    if (data?.error) return data.error;
  } catch {
    /* 非 JSON 响应，用兜底文案 */
  }
  return fallback;
}

function TimeoutCell({ submission }) {
  if (submission.timeout_level === 2) return <span style={{ color: '#c0392b', fontWeight: 600 }}>已超 2h</span>;
  if (submission.timeout_level === 1) return <span style={{ color: '#b7791f' }}>已超 1h</span>;
  return <span style={{ color: '#8a94a6' }}>—</span>;
}

export default function HubSubmissions() {
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState('1');
  const [error, setError] = useState('');
  const [detail, setDetail] = useState(null);
  const [newNames, setNewNames] = useState({});
  const [busy, setBusy] = useState(false);
  const [modalError, setModalError] = useState('');

  async function load() {
    const params = statusFilter ? `?status=${statusFilter}` : '';
    const res = await api.get(`/admin/hub/submissions${params}`);
    if (!res?.ok) {
      setError(await readError(res, '加载提交单失败'));
      setRows([]);
      return;
    }
    setError('');
    setRows(await res.json());
  }

  useEffect(() => { load(); }, [statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  function openDetail(row) {
    setDetail(row);
    setNewNames({});
    setModalError('');
  }

  async function callHub(path, body) {
    setBusy(true);
    setModalError('');
    try {
      const res = await api.post(`/admin/hub/${path}`, body ?? {});
      if (!res?.ok) {
        setModalError(await readError(res, '操作失败'));
        return null;
      }
      return await res.json();
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    const pending = allLines(detail).filter((line) => line.is_new_item && line.item_id == null);
    const missing = pending.find((line) => !(newNames[line.id] || '').trim());
    if (missing) {
      setModalError(`第 ${missing.line_no} 行是新品，必须填写正式商品名`);
      return;
    }
    const payload = {
      new_items: pending.map((line) => ({ line_id: line.id, item_name: newNames[line.id].trim() })),
    };
    const updated = await callHub(`submissions/${detail.id}/verify`, payload);
    if (updated) {
      setDetail(null);
      await load();
    }
  }

  async function rework() {
    const updated = await callHub(`submissions/${detail.id}/rework`);
    if (updated) {
      setDetail(null);
      await load();
    }
  }

  async function changeItem(line, sku) {
    const updated = await callHub(`submissions/${detail.id}/lines/${line.id}/change-item`, { item_id: sku.id });
    if (updated) setDetail(updated);
  }

  async function mergeDuplicate(line, sku) {
    const updated = await callHub(`submissions/${detail.id}/lines/${line.id}/merge-duplicate`, {
      existing_item_id: sku.id,
    });
    if (updated) setDetail(updated);
  }

  const columns = [
    { key: 'submission_no', label: '提交单号', mono: true },
    { key: 'orders', label: '订单号', render: (r) => orderSummary(r.orders) },
    { key: 'submitted_by', label: '提交人' },
    { key: 'submitted_at', label: '提交时间', render: (r) => formatDateTime(r.submitted_at) },
    { key: 'timeout_level', label: '超时', render: (r) => <TimeoutCell submission={r} /> },
    {
      key: 'actions',
      label: '',
      render: (r) => (
        <button
          className="btn btn-sm btn-primary"
          onClick={(e) => { e.stopPropagation(); openDetail(r); }}
        >
          核验
        </button>
      ),
    },
  ];

  const hasRejected = !!detail && detail.orders.some((order) => order.confirm_status === 'rejected');

  return (
    <div>
      <PageHeader title="Hub 提交单" />

      <div className="filter-bar">
        <select
          className="form-select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      {error && <div className="form-error" style={{ marginBottom: 12 }}>{error}</div>}

      <DataTable
        rowKey="id"
        columns={columns}
        data={rows}
        onRowClick={openDetail}
        emptyMessage="当前没有待处理的提交单"
      />

      {detail && (
        <Modal
          title={`核验提交单 ${detail.submission_no}`}
          size="wide"
          onClose={() => setDetail(null)}
          footer={
            <>
              <button className="btn" onClick={() => setDetail(null)}>关闭</button>
              {hasRejected ? (
                <button className="btn btn-primary" disabled={busy} onClick={rework}>
                  返工完成，回到运营确认
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  disabled={busy || detail.status !== 1}
                  onClick={verify}
                  title={detail.status !== 1 ? '只有待仓库处理（①）的批次可以核验' : '核验通过并生成待审核货号'}
                >
                  核验通过
                </button>
              )}
            </>
          }
        >
          {modalError && <div className="form-error" style={{ marginBottom: 12 }}>{modalError}</div>}

          {detail.remark && (
            <p style={{ color: '#5b6472' }}>批次备注：{detail.remark}</p>
          )}
          {hasRejected && (
            <div className="form-error" style={{ marginBottom: 12 }}>
              该批次有订单被运营驳回：请先修正货号或判重删号，再点「返工完成」。
            </div>
          )}

          {detail.orders.map((order) => (
            <div className="card" key={order.id}>
              <div className="card-title">
                订单 <strong>{order.order_no}</strong>
                <span style={{ marginLeft: 8, color: '#8a94a6' }}>
                  {CONFIRM_LABEL[order.confirm_status] || order.confirm_status}
                  {order.reject_count > 0 && ` · 已驳回 ${order.reject_count}/3`}
                </span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: 48 }}>行</th>
                    <th style={{ width: 160 }}>货号</th>
                    <th>商品名 / 描述</th>
                    <th style={{ width: 260 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {order.lines.map((line) => (
                    <tr key={line.id}>
                      <td>{line.line_no}</td>
                      <td>
                        <code>{line.sku_code || line.draft_sku_code || '待生成'}</code>
                        {line.is_new_item && <span style={{ marginLeft: 6, color: '#b7791f' }}>新品</span>}
                      </td>
                      <td>
                        {line.is_new_item && line.item_id == null ? (
                          <input
                            className="form-input"
                            placeholder="填写正式商品名（核验时据此生成待审核货号）"
                            value={newNames[line.id] || ''}
                            onChange={(e) => setNewNames({ ...newNames, [line.id]: e.target.value })}
                          />
                        ) : (
                          <>
                            {line.item_name || '—'}
                            {line.item_desc && <small style={{ color: '#8a94a6' }}> · {line.item_desc}</small>}
                          </>
                        )}
                      </td>
                      <td>
                        {line.item_id == null ? (
                          <small style={{ color: '#8a94a6' }}>核验通过后自动生成待审核货号</small>
                        ) : line.is_new_item ? (
                          <HubSkuPicker
                            placeholder="选已有货号 → 判重删号"
                            disabled={busy}
                            onPick={(sku) => mergeDuplicate(line, sku)}
                          />
                        ) : (
                          <HubSkuPicker
                            placeholder="搜索货号 → 改号"
                            disabled={busy}
                            onPick={(sku) => changeItem(line, sku)}
                          />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </Modal>
      )}
    </div>
  );
}

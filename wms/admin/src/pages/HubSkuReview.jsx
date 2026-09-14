import { useEffect, useState } from 'react';
import { api } from '../api.js';
import DataTable from '../components/DataTable.jsx';
import PageHeader from '../components/PageHeader.jsx';

// 待审核货号（code_status='draft'）的转正队列。
//
// draft 是不允许被提交单引用的，仓库在这里确认「不是已有商品」后转正，
// 货号本身不变，只翻状态位；转正会立即把货号推送到 sentry-wms 的 items，
// 否则后续下单会因为找不到货号映射而被拒（409 cross_system_lookup_miss）。
//
// 判重删号不在这里做：那需要知道货号挂在哪个提交单的哪一行，上下文在
// 「Hub 提交单」页的核验弹窗里。

function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('zh-CN', { hour12: false });
}

async function readError(res, fallback) {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (data?.error) return data.error;
  } catch {
    /* 非 JSON 响应 */
  }
  return fallback;
}

export default function HubSkuReview() {
  const [skus, setSkus] = useState([]);
  const [categoryNames, setCategoryNames] = useState({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState(null);

  async function load() {
    const [skuRes, categoryRes] = await Promise.all([
      api.get('/admin/hub/catalog/skus/drafts'),
      api.get('/admin/hub/catalog/categories'),
    ]);
    if (!skuRes?.ok) {
      setError(await readError(skuRes, '加载待审核货号失败'));
      setSkus([]);
    } else {
      setError('');
      setSkus(await skuRes.json());
    }
    if (categoryRes?.ok) {
      const categories = await categoryRes.json();
      setCategoryNames(
        Object.fromEntries(categories.map((category) => [category.id, category.category_name]))
      );
    }
  }

  useEffect(() => { load(); }, []);

  async function promote(sku) {
    setBusyId(sku.id);
    setError('');
    setNotice('');
    try {
      const res = await api.post(`/admin/hub/skus/${sku.id}/promote`, {});
      if (!res?.ok) {
        setError(await readError(res, `货号 ${sku.sku_code} 转正失败`));
        return;
      }
      const result = await res.json();
      setNotice(
        result.replayed
          ? `${sku.sku_code} 已经是正式货号，无需重复转正。`
          : `${sku.sku_code} 已转正，并已推送到 sentry-wms。`
      );
      await load();
    } finally {
      setBusyId(null);
    }
  }

  const columns = [
    { key: 'sku_code', label: '待审核货号', mono: true },
    { key: 'item_name', label: '商品名' },
    {
      key: 'category_id',
      label: '二级类目',
      render: (r) => categoryNames[r.category_id] || r.category_id,
    },
    { key: 'created_at', label: '建号时间', render: (r) => formatDateTime(r.created_at) },
    {
      key: 'actions',
      label: '',
      render: (r) => (
        <button
          className="btn btn-sm btn-primary"
          disabled={busyId === r.id}
          onClick={(e) => { e.stopPropagation(); promote(r); }}
        >
          {busyId === r.id ? '转正中…' : '转正'}
        </button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Hub 新品审核" />

      <p style={{ color: '#5b6472', marginTop: 0 }}>
        确认这些货号不是已有商品后点「转正」：货号不变，只翻状态位，并立即推送到 sentry-wms。
        若要判重删号（说明这其实是已有商品），请到「Hub 提交单」的核验弹窗里操作。
      </p>

      {error && <div className="form-error" style={{ marginBottom: 12 }}>{error}</div>}
      {notice && (
        <div className="card" style={{ marginBottom: 12, color: '#1e7a46' }}>{notice}</div>
      )}

      <DataTable
        rowKey="id"
        columns={columns}
        data={skus}
        emptyMessage="没有待审核的货号"
      />
    </div>
  );
}

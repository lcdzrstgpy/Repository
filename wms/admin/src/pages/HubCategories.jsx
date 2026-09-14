import { useEffect, useState } from 'react';
import { api } from '../api.js';
import PageHeader from '../components/PageHeader.jsx';
import Modal from '../components/Modal.jsx';

// Hub 类目主数据。类目树固定两层：
//   一级（家居用品）— code_prefix 必须为空
//   二级（杯具）    — 必须带 code_prefix，如 A001；货号 = 前缀-序号
//
// seq_counter 是「该类目已发出的最大序号」，只增不减，所以这里只读展示：
// 判重删号留下的空号不会回收，避免历史单据串号。

const PREFIX_PATTERN = /^[A-Z][0-9]{3,15}$/;

async function readError(res, fallback) {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail.map((item) => item.msg || JSON.stringify(item)).join('; ');
    }
    if (data?.error) return data.error;
  } catch {
    /* 非 JSON 响应 */
  }
  return fallback;
}

export default function HubCategories() {
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({ parent_id: '', category_name: '', code_prefix: '' });
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await api.get('/admin/hub/catalog/categories');
    if (!res?.ok) {
      setError(await readError(res, '加载类目失败'));
      setCategories([]);
      return;
    }
    setError('');
    setCategories(await res.json());
  }

  useEffect(() => { load(); }, []);

  function openForm(parentId) {
    setForm({ parent_id: parentId ? String(parentId) : '', category_name: '', code_prefix: '' });
    setFormError('');
    setFormOpen(true);
  }

  async function save() {
    const name = form.category_name.trim();
    if (!name) {
      setFormError('请填写类目名');
      return;
    }
    const isChild = !!form.parent_id;
    const prefix = form.code_prefix.trim().toUpperCase();
    if (isChild && !PREFIX_PATTERN.test(prefix)) {
      setFormError('二级类目必须填写编码前缀，格式如 A001（一个大写字母 + 3 位以上数字）');
      return;
    }

    setBusy(true);
    setFormError('');
    try {
      const res = await api.post('/admin/hub/catalog/categories', {
        category_name: name,
        parent_id: isChild ? Number(form.parent_id) : null,
        code_prefix: isChild ? prefix : null,
      });
      if (!res?.ok) {
        setFormError(await readError(res, '保存失败'));
        return;
      }
      setFormOpen(false);
      await load();
    } finally {
      setBusy(false);
    }
  }

  const roots = categories.filter((category) => category.parent_id === null);
  const childrenOf = (id) => categories.filter((category) => category.parent_id === id);

  return (
    <div>
      <PageHeader title="Hub 类目管理">
        <button className="btn btn-primary" onClick={() => openForm(null)}>新增一级类目</button>
      </PageHeader>

      <p style={{ color: '#5b6472', marginTop: 0 }}>
        货号由「二级类目的编码前缀 + 该类目下一个序号」生成，例如杯具挂 <code>A001</code> 时，
        第一个商品是 <code>A001-1</code>。第三层（玻璃杯 / 马克杯）是商品名，不是类目，由仓库在商品档案里填。
      </p>

      {error && <div className="form-error" style={{ marginBottom: 12 }}>{error}</div>}

      {roots.length === 0 && !error && (
        <div className="card" style={{ color: '#8a94a6' }}>还没有类目，先新增一个一级类目。</div>
      )}

      {roots.map((root) => (
        <div className="card" key={root.id}>
          <div className="card-title">
            {root.category_name}
            <button
              className="btn btn-sm"
              style={{ marginLeft: 12 }}
              onClick={() => openForm(root.id)}
            >
              新增二级类目
            </button>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>二级类目</th>
                <th style={{ width: 140 }}>编码前缀</th>
                <th style={{ width: 140 }}>已发出序号</th>
                <th style={{ width: 100 }}>状态</th>
              </tr>
            </thead>
            <tbody>
              {childrenOf(root.id).map((child) => (
                <tr key={child.id}>
                  <td>{child.category_name}</td>
                  <td><code>{child.code_prefix}</code></td>
                  <td>{child.seq_counter}</td>
                  <td>{child.is_active ? '启用' : '停用'}</td>
                </tr>
              ))}
              {childrenOf(root.id).length === 0 && (
                <tr>
                  <td colSpan={4} style={{ color: '#8a94a6' }}>还没有二级类目，货号前缀挂在这一层。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ))}

      {formOpen && (
        <Modal
          title={form.parent_id ? '新增二级类目' : '新增一级类目'}
          onClose={() => setFormOpen(false)}
          footer={
            <>
              <button className="btn" onClick={() => setFormOpen(false)}>取消</button>
              <button className="btn btn-primary" disabled={busy} onClick={save}>
                {busy ? '保存中…' : '保存'}
              </button>
            </>
          }
        >
          {formError && <div className="form-error" style={{ marginBottom: 12 }}>{formError}</div>}
          <div className="form-group">
            <label>类目名</label>
            <input
              className="form-input"
              autoFocus
              value={form.category_name}
              onChange={(e) => setForm({ ...form, category_name: e.target.value })}
              placeholder="如 家居用品 / 杯具"
            />
          </div>
          {form.parent_id && (
            <div className="form-group">
              <label>编码前缀</label>
              <input
                className="form-input"
                value={form.code_prefix}
                onChange={(e) => setForm({ ...form, code_prefix: e.target.value.toUpperCase() })}
                placeholder="如 A001"
              />
              <small style={{ color: '#8a94a6' }}>
                全库唯一。一级类目占一个字母，二级在该字母下顺序编号。
              </small>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

// 仓库端「改号 / 判重」用的货号检索。
//
// 走 wms 代理 → Hub 的 /api/v1/warehouse/catalog/skus/search，只返回可被
// 提交单引用的正式货号（code_status='active'），所以 draft 不会出现在
// 候选里。输入停顿 250ms 才发请求，避免逐字符打库。
export default function HubSkuPicker({ placeholder = '搜索货号或商品名', onPick, disabled }) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    const keyword = query.trim();
    if (!keyword) return undefined;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.get(
          `/admin/hub/catalog/skus/search?q=${encodeURIComponent(keyword)}`
        );
        if (res?.ok) {
          setOptions(await res.json());
          setOpen(true);
        }
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [query]);

  // 清空放在事件里而不是 effect 里：effect 内同步 setState 会触发级联渲染，
  // 新版的 react-hooks 规则会直接报错。
  function changeQuery(value) {
    setQuery(value);
    if (!value.trim()) {
      setOptions([]);
      setOpen(false);
    }
  }

  function pick(sku) {
    setQuery('');
    setOptions([]);
    setOpen(false);
    onPick(sku);
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        className="form-input"
        placeholder={placeholder}
        value={query}
        disabled={disabled}
        onChange={(e) => changeQuery(e.target.value)}
        onFocus={() => options.length > 0 && setOpen(true)}
      />
      {loading && <small style={{ color: '#8a94a6' }}>检索中…</small>}
      {open && options.length > 0 && (
        <div className="card" style={{ position: 'absolute', zIndex: 20, width: '100%', maxHeight: 220, overflowY: 'auto', marginTop: 2 }}>
          {options.map((sku) => (
            <button
              key={sku.id}
              type="button"
              className="btn btn-sm"
              style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 2 }}
              onClick={() => pick(sku)}
            >
              <strong>{sku.sku_code}</strong> · {sku.item_name}
            </button>
          ))}
        </div>
      )}
      {open && !loading && query.trim() && options.length === 0 && (
        <small style={{ color: '#8a94a6' }}>没有匹配的正式货号</small>
      )}
    </div>
  );
}

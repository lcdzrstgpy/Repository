import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Sku } from '../types'
import { Icon } from './Icon'

export function SkuSearch({ value, disabled, onSelect }: { value: string; disabled?: boolean; onSelect: (sku: Sku | null, input: string) => void }) {
  const [query, setQuery] = useState(value)
  const [results, setResults] = useState<Sku[]>([])
  const [open, setOpen] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => setQuery(value), [value])
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const search = (input: string) => {
    setQuery(input); onSelect(null, input)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      try { setResults(await api.catalog.searchSkus(input)); setOpen(true) } catch { setResults([]) }
    }, 180)
  }
  return <div className="sku-search">
    <span className="input-icon"><Icon name="search" size={16} /></span>
    <input value={query} disabled={disabled} placeholder="搜索商品名或货号" onChange={(event) => search(event.target.value)} onFocus={() => { if (!disabled) search(query) }} onBlur={() => window.setTimeout(() => setOpen(false), 150)} />
    {open && !disabled && <div className="sku-results">
      {results.length ? results.map((sku) => <button type="button" key={sku.id} onMouseDown={() => { setQuery(sku.skuCode); onSelect(sku, sku.skuCode); setOpen(false) }}>
        <strong>{sku.skuCode}</strong><span>{sku.itemName}</span><small>{sku.categoryPath}</small>
      </button>) : <div className="search-empty">未找到可用货号</div>}
    </div>}
  </div>
}

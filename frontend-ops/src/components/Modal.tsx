import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Icon } from './Icon'

export function Modal({ title, children, onClose, footer }: { title: string; children: ReactNode; onClose: () => void; footer: ReactNode }) {
  useEffect(() => {
    const listener = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [onClose])
  return <div className="modal-backdrop" role="dialog" aria-modal="true">
    <div className="modal">
      <div className="modal-head"><h3>{title}</h3><button className="icon-button" onClick={onClose} aria-label="关闭"><Icon name="x" /></button></div>
      <div className="modal-body">{children}</div>
      <div className="modal-footer">{footer}</div>
    </div>
  </div>
}

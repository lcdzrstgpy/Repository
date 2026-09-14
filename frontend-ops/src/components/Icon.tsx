import type { SVGProps } from 'react'

const paths: Record<string, React.ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  list: <><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></>,
  chevron: <path d="M9 18l6-6-6-6"/>,
  trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v6M14 11v6"/></>,
  box: <><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><path d="M3.3 7l8.7 5 8.7-5M12 22V12"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  check: <path d="M20 6L9 17l-5-5"/>,
  alert: <><path d="M10.3 3.5L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.5a2 2 0 00-3.4 0z"/><path d="M12 9v4M12 17h.01"/></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  x: <><path d="M18 6L6 18M6 6l12 12"/></>,
  file: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
}

export function Icon({ name, size = 18, ...props }: SVGProps<SVGSVGElement> & { name: keyof typeof paths; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>
}

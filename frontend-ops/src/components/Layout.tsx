import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { Icon } from './Icon'

const titleMap: Record<string, { title: string; subtitle: string }> = {
  '/submit': { title: '批次提交', subtitle: '创建一批新的代发申请' },
  '/requests': { title: '我的申请', subtitle: '跟踪申请状态与履约进度' },
}

export function Layout() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()
  const location = useLocation()
  const [demo, setDemo] = useState(false)
  useEffect(() => {
    const onDemo = () => setDemo(true)
    window.addEventListener('demo-fallback', onDemo)
    return () => window.removeEventListener('demo-fallback', onDemo)
  }, [])
  const base = location.pathname.startsWith('/requests') || location.pathname.startsWith('/confirm') ? '/requests' : '/submit'
  const meta = titleMap[base]
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Icon name="box" size={22} /></span><div><strong>NEXUS</strong><small>仓储运营中枢</small></div></div>
      <nav>
        <NavLink to="/submit"><Icon name="plus" /><span>批次提交</span></NavLink>
        <NavLink to="/requests" className={({ isActive }) => isActive || base === '/requests' ? 'active' : ''}><Icon name="list" /><span>我的申请</span></NavLink>
      </nav>
      <div className="sidebar-foot">
        <div className="user-card"><span className="avatar">{user?.displayName.slice(0, 1)}</span><div><strong>{user?.displayName}</strong><small>运营专员</small></div><button className="icon-button" aria-label="退出登录" onClick={() => { logout(); navigate('/login') }}><Icon name="logout" /></button></div>
        <div className="system-state"><i /> 中枢服务连接正常</div>
      </div>
    </aside>
    <main className="main">
      <header className="topbar"><div><h1>{meta.title}</h1><p>{meta.subtitle}</p></div><div className="top-actions">{demo && <span className="demo-pill">DEV · DEMO FALLBACK</span>}<span className="date-pill">2026 / 09 / 14</span></div></header>
      <div className="content"><Outlet /></div>
    </main>
  </div>
}

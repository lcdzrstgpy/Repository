import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { useAuthStore } from '../store/auth'

export function LoginPage() {
  const token = useAuthStore((state) => state.token)
  const setSession = useAuthStore((state) => state.setSession)
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('operator')
  const [password, setPassword] = useState('ops2026')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  if (token) return <Navigate to="/submit" replace />
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError('')
    if (!username.trim() || !password) return setError('请输入运营账号和密码')
    setLoading(true)
    try {
      const result = await api.auth.login(username.trim(), password)
      setSession(result.accessToken, result.user)
      const from = (location.state as { from?: string } | null)?.from ?? '/submit'
      navigate(from, { replace: true })
    } catch (reason) { setError(reason instanceof Error ? reason.message : '登录失败') }
    finally { setLoading(false) }
  }
  return <div className="login-page">
    <section className="login-visual">
      <div className="login-brand"><span className="brand-mark"><Icon name="box" size={24} /></span><strong>NEXUS</strong></div>
      <div className="visual-copy"><span className="eyebrow">OPERATIONS CONTROL</span><h1>让每一笔履约<br />清晰、可控、可追溯</h1><p>跨境代发仓运营中枢，为提交、确认与履约协作提供唯一事实源。</p></div>
      <div className="visual-grid"><span/><span/><span/><span/><span/><span/></div>
      <div className="visual-stats"><div><strong>6</strong><span>状态节点</span></div><div><strong>100%</strong><span>订单级追踪</span></div><div><strong>&lt; 1h</strong><span>目标响应</span></div></div>
    </section>
    <section className="login-panel">
      <form className="login-form" onSubmit={submit}>
        <div className="mobile-brand"><span className="brand-mark"><Icon name="box" size={20} /></span><strong>NEXUS</strong></div>
        <span className="eyebrow">运营工作台</span><h2>欢迎回来</h2><p className="muted">使用独立运营账号登录中枢系统</p>
        <label>运营账号<input autoFocus value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" placeholder="请输入账号" /></label>
        <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="请输入密码" /></label>
        {error && <div className="form-error"><Icon name="alert" size={16}/>{error}</div>}
        <button className="button button-primary login-button" disabled={loading}>{loading ? '正在验证…' : '登录运营工作台'}<Icon name="arrow" /></button>
        {import.meta.env.DEV && <div className="demo-hint"><span>开发预览</span> API 不可用时自动启用本地 Demo 数据</div>}
      </form>
      <small className="login-foot">NEXUS WAREHOUSE ERP · OPS CONSOLE</small>
    </section>
  </div>
}

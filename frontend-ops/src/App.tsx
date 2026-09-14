import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { useAuthStore } from './store/auth'
import { LoginPage } from './pages/LoginPage'
import { SubmitPage } from './pages/SubmitPage'
import { RequestsPage } from './pages/RequestsPage'
import { ConfirmPage } from './pages/ConfirmPage'

function Guard({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((state) => state.token)
  const location = useLocation()
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

export default function App() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<Guard><Layout /></Guard>}>
      <Route path="/submit" element={<SubmitPage />} />
      <Route path="/requests" element={<RequestsPage />} />
      <Route path="/requests/:id" element={<RequestsPage />} />
      <Route path="/confirm/:id" element={<ConfirmPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/submit" replace />} />
  </Routes>
}

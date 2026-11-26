import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthGuard, GuestGuard } from '@/components/AuthGuard'
import AppLayout from '@/components/AppLayout'
import CoachPage from '@/pages/CoachPage'
import CorrectionStreamPage from '@/pages/CorrectionStreamPage'
import Login from '@/pages/Login'
import { useAuth } from '@/store/auth-context'
import { AuthProvider } from '@/store/auth'

function RootRedirect() {
  const { user, ready } = useAuth()
  if (!ready) return null
  return <Navigate to={user ? '/correction/stream' : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route element={<GuestGuard />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route element={<AuthGuard />}>
            <Route element={<AppLayout />}>
              <Route path="/correction/stream" element={<CorrectionStreamPage />} />
              <Route
                path="/correction"
                element={<Navigate to="/correction/stream" replace />}
              />
              <Route path="/coach" element={<CoachPage />} />
            </Route>
          </Route>
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

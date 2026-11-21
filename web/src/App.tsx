import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthGuard, GuestGuard } from '@/components/AuthGuard'
import AppLayout from '@/components/AppLayout'
import CorrectionPage from '@/pages/CorrectionPage'
import Login from '@/pages/Login'
import NotesPage from '@/pages/NotesPage'
import StreamCorrectionPage from '@/pages/StreamCorrectionPage'
import { useAuth } from '@/store/auth-context'
import { AuthProvider } from '@/store/auth'
import { ConversationProvider } from '@/store/conversation'

function RootRedirect() {
  const { user, ready } = useAuth()
  if (!ready) return null
  return <Navigate to={user ? '/correction' : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/stream" element={<StreamCorrectionPage />} />
          <Route element={<GuestGuard />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route element={<AuthGuard />}>
            <Route element={<AppLayout />}>
              <Route
                path="/correction"
                element={
                  <ConversationProvider>
                    <CorrectionPage />
                  </ConversationProvider>
                }
              />
              <Route path="/notes" element={<NotesPage />} />
            </Route>
          </Route>
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

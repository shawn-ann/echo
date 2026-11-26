import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '@/store/auth-context'

export function AuthGuard() {
  const { user, ready } = useAuth()
  if (!ready) return null
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

export function GuestGuard() {
  const { user, ready } = useAuth()
  if (!ready) return null
  if (user) return <Navigate to="/correction/stream" replace />
  return <Outlet />
}

import { createContext, useContext } from 'react'

import type { User } from '@/api/auth'

export interface AuthState {
  user: User | null
  ready: boolean
  login: (username: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

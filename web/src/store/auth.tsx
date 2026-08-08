import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import * as authApi from '@/api/auth'
import { clearToken, getToken, setToken } from '@/api/client'
import { AuthContext, type AuthState } from '@/store/auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<authApi.User | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function init() {
      const token = getToken()
      if (!token) {
        setReady(true)
        return
      }
      try {
        const me = await authApi.fetchMe()
        if (!cancelled) setUser(me)
      } catch {
        clearToken()
      } finally {
        if (!cancelled) setReady(true)
      }
    }

    init()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const result = await authApi.login(username, password)
    setToken(result.token)
    setUser(result.user)
    return result.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // 幂等：token 已失效也清除本地登录态
    }
    clearToken()
    setUser(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, ready, login, logout }),
    [user, ready, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

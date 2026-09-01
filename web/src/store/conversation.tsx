import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'

import * as messagesApi from '@/api/messages'
import { ApiError } from '@/api/client'
import { useAuth } from '@/store/auth-context'
import { ConversationContext } from '@/store/conversation-context'

export function ConversationProvider({ children }: { children: ReactNode }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<messagesApi.Message[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionExpired, setSessionExpired] = useState(false)
  const mounted = useRef(true)
  const tempIdRef = useRef(0)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const data = await messagesApi.fetchMessages()
      if (mounted.current) setMessages(data)
    } catch {
      // 历史加载失败：保持空态，发送时重试
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const submit = useCallback(
    async (tempId: string, content: string): Promise<boolean> => {
      setPending(true)
      setError(null)
      setSessionExpired(false)
      try {
        const result = await messagesApi.submitMessage(content)
        if (mounted.current) {
          setMessages((prev) => [
            ...prev.filter((m) => m.id !== tempId),
            result.user_message,
            result.assistant_message,
          ])
        }
        return true
      } catch (err) {
        if (mounted.current) {
          if (err instanceof ApiError && err.status === 401) {
            setSessionExpired(true)
            setError('会话已过期，请重新登录')
          } else {
            setError(err instanceof ApiError ? err.message : '请求失败，请重试')
          }
        }
        return false
      } finally {
        if (mounted.current) setPending(false)
      }
    },
    [],
  )

  const send = useCallback(
    async (content: string): Promise<boolean> => {
      tempIdRef.current += 1
      const tempId = `tmp-${tempIdRef.current}`
      const temp: messagesApi.Message = {
        id: tempId,
        role: 'user',
        type: 'correction',
        content,
        report: null,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, temp])
      return submit(tempId, content)
    },
    [submit],
  )

  const retry = useCallback(
    async (tempId: string, content: string): Promise<boolean> => {
      return submit(tempId, content)
    },
    [submit],
  )

  const relogin = useCallback(async () => {
    await logout()
    navigate('/login', { replace: true })
  }, [logout, navigate])

  const value = useMemo(
    () => ({ messages, pending, error, sessionExpired, load, send, retry, relogin }),
    [messages, pending, error, sessionExpired, load, send, retry, relogin],
  )
  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>
}

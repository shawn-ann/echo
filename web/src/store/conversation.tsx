import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import * as messagesApi from '@/api/messages'
import { ApiError } from '@/api/client'
import { ConversationContext } from '@/store/conversation-context'

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<messagesApi.Message[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

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

  const send = useCallback(async (content: string) => {
    setPending(true)
    setError(null)
    const temp: messagesApi.Message = {
      id: `tmp-${Date.now()}`,
      role: 'user',
      type: 'correction',
      content,
      report: null,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, temp])
    try {
      const result = await messagesApi.submitMessage(content)
      if (mounted.current) {
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== temp.id),
          result.user_message,
          result.assistant_message,
        ])
      }
    } catch (err) {
      if (mounted.current) {
        setMessages((prev) => prev.filter((m) => m.id !== temp.id))
        setError(err instanceof ApiError ? err.message : '请求失败，请重试')
      }
    } finally {
      if (mounted.current) setPending(false)
    }
  }, [])

  const value = { messages, pending, error, load, send }
  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>
}

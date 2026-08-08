import { createContext, useContext } from 'react'

import type { Message } from '@/api/messages'

export interface ConversationState {
  messages: Message[]
  pending: boolean
  error: string | null
  sessionExpired: boolean
  load: () => Promise<void>
  send: (content: string) => Promise<boolean>
  retry: (tempId: string, content: string) => Promise<boolean>
  relogin: () => void
}

export const ConversationContext = createContext<ConversationState | null>(null)

export function useConversation(): ConversationState {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within ConversationProvider')
  return ctx
}

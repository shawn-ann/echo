import type { ChatError, ChatRewrite } from '@/api/chat'

export interface UserChatItem {
  id: string
  role: 'user'
  text: string
}

export interface CorrectionChatItem {
  id: string
  role: 'assistant'
  kind: 'correction'
  status: 'streaming' | 'done' | 'error'
  turnId: string
  errorsLoaded: boolean
  errors: ChatError[]
  minimal: ChatRewrite | null
  fluency: ChatRewrite | null
  degraded: string[]
  error: string | null
}

export interface TextChatItem {
  id: string
  role: 'assistant'
  kind: 'text'
  status: 'streaming' | 'done' | 'error'
  text: string
  error: string | null
}

export interface PendingChatItem {
  id: string
  role: 'assistant'
  kind: 'pending'
  status: 'streaming'
  error: string | null
}

export type ChatItem =
  | UserChatItem
  | CorrectionChatItem
  | TextChatItem
  | PendingChatItem

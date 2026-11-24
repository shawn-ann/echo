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
  sourceText: string
  startedAt: number
  thinkingMs: number | null
  doneMs: number | null
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
  startedAt: number
  thinkingMs: number | null
  doneMs: number | null
  text: string
  error: string | null
}

export interface PendingChatItem {
  id: string
  role: 'assistant'
  kind: 'pending'
  status: 'streaming'
  sourceText: string
  startedAt: number
  error: null
}

export type ChatItem =
  | UserChatItem
  | CorrectionChatItem
  | TextChatItem
  | PendingChatItem

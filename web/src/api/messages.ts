import { http } from './client'

export interface ErrorBlock {
  category: string
  fragment: string
  explanation: string
  correction: string
}

export interface RewriteOption {
  text: string
  explanation: string
}

export interface RewriteSection {
  minimal: RewriteOption
  natural: RewriteOption
}

export interface CorrectionReport {
  has_errors: boolean
  errors: ErrorBlock[]
  rewrite: RewriteSection | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  type: string
  content: string | null
  report: CorrectionReport | null
  created_at: string
}

export interface SubmitResult {
  user_message: Message
  assistant_message: Message
}

export async function fetchMessages(): Promise<Message[]> {
  const data = await http.get<{ messages: Message[] }>('/messages')
  return data.messages
}

export async function submitMessage(content: string): Promise<SubmitResult> {
  return http.post<SubmitResult>('/messages', { content })
}

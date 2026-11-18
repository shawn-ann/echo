import { http } from './client'

export interface ErrorBlock {
  category: string
  fragment: string
  explanation: string
  correction: string
}

export interface RewriteOption {
  text: string
  note: string
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
  type: 'correction' | 'report'
  content: string | null
  report: CorrectionReport | null
  created_at: string
}

export interface SubmitResult {
  user_message: Message
  assistant_message: Message
}

/** 兼容历史报告（error_type / 缺失 has_errors / rewrite 为 null）与 V3 新契约。 */
export function normalizeReport(raw: any): CorrectionReport | null {
  if (!raw) return null
  const errors: ErrorBlock[] = (raw.errors ?? []).map((e: any) => ({
    category: e.category ?? e.error_type ?? '',
    fragment: e.fragment ?? '',
    explanation: e.explanation ?? '',
    correction: e.correction ?? '',
  }))
  return {
    has_errors: typeof raw.has_errors === 'boolean' ? raw.has_errors : errors.length > 0,
    errors,
    rewrite: raw.rewrite?.minimal && raw.rewrite?.natural ? raw.rewrite : null,
  }
}

function normalizeMessage(m: Message): Message {
  return { ...m, report: normalizeReport(m.report) }
}

export async function fetchMessages(): Promise<Message[]> {
  const data = await http.get<{ messages: Message[] }>('/messages')
  return data.messages.map(normalizeMessage)
}

export async function submitMessage(content: string): Promise<SubmitResult> {
  const data = await http.post<SubmitResult>('/messages', { content })
  return {
    user_message: normalizeMessage(data.user_message),
    assistant_message: normalizeMessage(data.assistant_message),
  }
}

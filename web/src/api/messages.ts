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

/** 早期产物把 category 存成英文枚举，需回退到 error_type。 */
const LEGACY_CATEGORIES = new Set(['grammar', 'collocation', 'chinglish', 'style'])

function pickCategory(e: any): string {
  const cat = e?.category
  if (typeof cat === 'string' && cat !== '' && !LEGACY_CATEGORIES.has(cat)) return cat
  if (typeof e?.error_type === 'string' && e.error_type !== '') return e.error_type
  return typeof cat === 'string' ? cat : ''
}

function isRewriteOption(o: any): boolean {
  return typeof o?.text === 'string' && typeof o?.note === 'string'
}

/** 兼容历史报告（error_type / 缺失 has_errors / rewrite 为 null 或结构不全）与 V3 新契约。 */
export function normalizeReport(raw: any): CorrectionReport | null {
  if (!raw) return null
  const errors: ErrorBlock[] = (raw.errors ?? []).map((e: any) => ({
    category: pickCategory(e),
    fragment: e?.fragment ?? '',
    explanation: e?.explanation ?? '',
    correction: e?.correction ?? '',
  }))
  const rewriteOk = isRewriteOption(raw.rewrite?.minimal) && isRewriteOption(raw.rewrite?.natural)
  return {
    has_errors: typeof raw.has_errors === 'boolean' ? raw.has_errors : errors.length > 0,
    errors,
    rewrite: rewriteOk ? raw.rewrite : null,
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

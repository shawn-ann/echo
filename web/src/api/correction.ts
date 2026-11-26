import type { CoachError, CoachRewrites, CoachVariant } from './coach'
import { API_BASE, getToken, http } from './client'

export interface CorrectionReport {
  mode: 'correct'
  has_errors: boolean
  errors: CoachError[]
  rewrites: CoachRewrites
}

export type CorrectionEvent =
  | { kind: 'report_start'; schema_version: number; mode: 'correct' }
  | { kind: 'reasoning'; text: string }
  | ({ kind: 'error_added'; index: number } & CoachError)
  | { kind: 'rewrite_ready'; variant: CoachVariant; text: string; note?: string }
  | { kind: 'done'; report: CorrectionReport | null; raw?: string }
  | { kind: 'error'; code: string; message: string }

function parseFrame(frame: string): CorrectionEvent | null {
  let eventName = ''
  const dataLines: string[] = []

  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith(':')) continue
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!eventName || dataLines.length === 0) return null

  let data: Record<string, unknown>
  try {
    data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  } catch {
    return null
  }

  switch (eventName) {
    case 'report_start':
      return {
        kind: 'report_start',
        schema_version: Number(data.schema_version ?? 1),
        mode: 'correct',
      }
    case 'reasoning':
      return { kind: 'reasoning', text: String(data.text ?? '') }
    case 'error_added':
      return {
        kind: 'error_added',
        index: Number(data.index ?? 0),
        severity:
          data.severity === 'Critical'
            ? 'Critical'
            : data.severity === 'Minor'
              ? 'Minor'
              : 'Major',
        fragment: String(data.fragment ?? ''),
        type: String(data.type ?? ''),
        reason: String(data.reason ?? ''),
        fix: String(data.fix ?? ''),
      }
    case 'rewrite_ready': {
      const variant =
        data.variant === 'formal' ||
        data.variant === 'casual' ||
        data.variant === 'minimal'
          ? data.variant
          : 'minimal'
      return {
        kind: 'rewrite_ready',
        variant,
        text: String(data.text ?? ''),
        note: data.note ? String(data.note) : undefined,
      }
    }
    case 'done':
      return {
        kind: 'done',
        report: (data.report ?? null) as CorrectionReport | null,
        raw: data.raw ? String(data.raw) : undefined,
      }
    case 'error':
      return {
        kind: 'error',
        code: String(data.code ?? 'CORRECTION_STREAM_FAILED'),
        message: String(data.message ?? '请求失败，请重试'),
      }
    default:
      return null
  }
}

export async function streamCorrection(
  content: string,
  onEvent: (event: CorrectionEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  const token = getToken()
  try {
    res = await fetch(`${API_BASE}/correction/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content, mode: 'correction' }),
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new Error('无法连接后端服务，请确认后端已启动')
  }

  if (!res.ok) throw new Error(`请求失败（${res.status}）`)
  if (!res.body) throw new Error('当前浏览器不支持流式响应')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const event = parseFrame(frame)
      if (event) onEvent(event)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    const event = parseFrame(buffer)
    if (event) onEvent(event)
  }
}


export interface StoredRewrite {
  id: 'formal' | 'casual' | 'minimal' | string
  text: string
  note?: string
}

export interface StoredCorrection {
  id: string
  mode: string
  source_text: string
  report: {
    schema_version: number
    errors: CoachError[]
    rewrites: StoredRewrite[] | CoachRewrites
  }
  schema_version: number
  duration_ms: number | null
  model: string | null
  created_at: string
}

export async function fetchCorrections(): Promise<StoredCorrection[]> {
  const data = await http.get<{ corrections: StoredCorrection[] }>('/corrections')
  return data.corrections
}

export function normalizeStoredReport(report: StoredCorrection['report']): CorrectionReport {
  const rewrites: Partial<Record<CoachVariant, { text: string; note?: string }>> = {}
  if (Array.isArray(report.rewrites)) {
    for (const item of report.rewrites) {
      if (item.id === 'formal' || item.id === 'casual' || item.id === 'minimal') {
        rewrites[item.id] = { text: item.text, note: item.note }
      }
    }
  } else {
    Object.assign(rewrites, report.rewrites)
  }
  return {
    mode: 'correct',
    has_errors: report.errors.length > 0,
    errors: report.errors,
    rewrites: rewrites as CorrectionReport['rewrites'],
  }
}

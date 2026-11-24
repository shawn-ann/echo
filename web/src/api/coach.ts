import { API_BASE } from './client'

export type CoachMode = 'correct' | 'answer'
export type CoachVariant = 'formal' | 'casual' | 'minimal'
export type CoachSeverity = 'Critical' | 'Major' | 'Minor'

export interface CoachHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface CoachError {
  severity: CoachSeverity
  fragment: string
  type: string
  reason: string
  fix: string
}

export interface CoachRewrite {
  text: string
  note?: string | null
}

export interface CoachRewrites {
  formal: CoachRewrite
  casual: CoachRewrite
  minimal: CoachRewrite
}

export interface CoachLearning {
  pattern: string
  wrong: string
  right: string
  rule: string
  examples: string[]
}

export type CoachReport =
  | {
      mode: 'correct'
      has_errors: boolean
      errors: CoachError[]
      rewrites: CoachRewrites
      learnings: CoachLearning[]
    }
  | { mode: 'answer'; answer: string }

export type CoachEvent =
  | { kind: 'report_start'; schema_version: number; mode: CoachMode }
  | { kind: 'reasoning'; text: string }
  | ({ kind: 'error_added'; index: number } & CoachError)
  | {
      kind: 'rewrite_ready'
      variant: CoachVariant
      text: string
      note?: string
    }
  | ({ kind: 'learning_added'; index: number } & CoachLearning)
  | { kind: 'answer_delta'; text: string }
  | { kind: 'done'; report: CoachReport | null; raw?: string }
  | { kind: 'error'; code: string; message: string }

function parseFrame(frame: string): CoachEvent | null {
  let eventName = ''
  const dataLines: string[] = []

  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
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
        mode: data.mode === 'answer' ? 'answer' : 'correct',
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
    case 'learning_added':
      return {
        kind: 'learning_added',
        index: Number(data.index ?? 0),
        pattern: String(data.pattern ?? ''),
        wrong: String(data.wrong ?? ''),
        right: String(data.right ?? ''),
        rule: String(data.rule ?? ''),
        examples: Array.isArray(data.examples)
          ? data.examples.map((item) => String(item))
          : [],
      }
    case 'answer_delta':
      return { kind: 'answer_delta', text: String(data.text ?? '') }
    case 'done':
      return {
        kind: 'done',
        report: (data.report ?? null) as CoachReport | null,
        raw: data.raw ? String(data.raw) : undefined,
      }
    case 'error':
      return {
        kind: 'error',
        code: String(data.code ?? 'COACH_STREAM_FAILED'),
        message: String(data.message ?? '请求失败，请重试'),
      }
    default:
      return null
  }
}

export async function streamCoach(
  messages: CoachHistoryMessage[],
  onEvent: (event: CoachEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/coach/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
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

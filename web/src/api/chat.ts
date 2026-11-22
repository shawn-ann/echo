import { API_BASE } from './client'

export interface ChatError {
  category: string
  fragment: string
  correction: string
  explanation: string
}

export interface ChatRewrite {
  text: string
  note: string
}

export type ChatEvent =
  | { type: 'errors'; has_errors: boolean; errors: ChatError[] }
  | { type: 'minimal'; text: string; note: string }
  | { type: 'fluency'; text: string; note: string }
  | { type: 'rewrite_degraded'; stage: 'minimal' | 'fluency'; message: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done'; has_errors: boolean }

function parseFrame(frame: string): ChatEvent | null {
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
  const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>

  switch (eventName) {
    case 'errors':
      return {
        type: 'errors',
        has_errors: Boolean(data.has_errors),
        errors: (data.errors ?? []) as ChatError[],
      }
    case 'minimal':
      return {
        type: 'minimal',
        text: String(data.text ?? ''),
        note: String(data.note ?? ''),
      }
    case 'fluency':
      return {
        type: 'fluency',
        text: String(data.text ?? ''),
        note: String(data.note ?? ''),
      }
    case 'rewrite_degraded':
      return {
        type: 'rewrite_degraded',
        stage: data.stage === 'fluency' ? 'fluency' : 'minimal',
        message: String(data.message ?? ''),
      }
    case 'error':
      return {
        type: 'error',
        code: String(data.code ?? 'CHAT_STREAM_FAILED'),
        message: String(data.message ?? '请求失败，请重试'),
      }
    case 'done':
      return { type: 'done', has_errors: Boolean(data.has_errors) }
    default:
      return null
  }
}

export async function streamCorrection(
  content: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
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

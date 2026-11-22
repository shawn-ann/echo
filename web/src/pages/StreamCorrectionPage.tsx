import { useEffect, useRef, useState } from 'react'

import {
  streamCorrection,
  type ChatEvent,
  type StreamOptions,
} from '@/api/chat'
import ChatComposer from '@/components/correction/ChatComposer'
import ChatCorrectionMessage from '@/components/correction/ChatCorrectionMessage'
import ChatTextMessage from '@/components/correction/ChatTextMessage'
import UserBubble from '@/components/correction/UserBubble'
import { Button } from '@/components/ui/button'
import type { ChatItem, CorrectionChatItem, TextChatItem } from '@/types/chat'

interface SelectedTarget {
  turnId: string
  errorId: string
}

export default function StreamCorrectionPage() {
  const [items, setItems] = useState<ChatItem[]>([])
  const [content, setContent] = useState('')
  const [threadId, setThreadId] = useState<string | null>(null)
  const [selected, setSelected] = useState<SelectedTarget | null>(null)
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const idRef = useRef(0)
  const lastRequestRef = useRef<{ content: string; options: StreamOptions } | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [items, error])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const nextId = () => {
    idRef.current += 1
    return `m${idRef.current}`
  }

  function updateItem(id: string, updater: (item: ChatItem) => ChatItem) {
    setItems((prev) => prev.map((item) => (item.id === id ? updater(item) : item)))
  }

  function upsertCorrection(id: string, patch: Partial<CorrectionChatItem>) {
    setItems((prev) => {
      const exists = prev.some((item) => item.id === id)
      if (!exists) {
        return [
          ...prev,
          {
            id,
            role: 'assistant',
            kind: 'correction',
            status: 'streaming',
            turnId: patch.turnId ?? '',
            errorsLoaded: patch.errorsLoaded ?? false,
            errors: patch.errors ?? [],
            minimal: patch.minimal ?? null,
            fluency: patch.fluency ?? null,
            degraded: patch.degraded ?? [],
            error: patch.error ?? null,
          },
        ]
      }
      return prev.map((item) =>
        item.id === id && item.role === 'assistant' && item.kind === 'correction'
          ? { ...item, ...patch }
          : item,
      )
    })
  }

  function upsertText(id: string, patch: Partial<TextChatItem>) {
    setItems((prev) => {
      const exists = prev.some((item) => item.id === id)
      if (!exists) {
        return [
          ...prev,
          {
            id,
            role: 'assistant',
            kind: 'text',
            status: 'streaming',
            text: patch.text ?? '',
            error: patch.error ?? null,
          },
        ]
      }
      return prev.map((item) =>
        item.id === id && item.role === 'assistant' && item.kind === 'text'
          ? { ...item, ...patch }
          : item,
      )
    })
  }

  function appendDegraded(id: string, value: string) {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id && item.role === 'assistant' && item.kind === 'correction'
          ? { ...item, degraded: [...item.degraded, value] }
          : item,
      ),
    )
  }

  function handleEvent(event: ChatEvent, assistantId: string, controller: AbortController) {
    if (controller.signal.aborted) return
    switch (event.type) {
      case 'thread':
        setThreadId(event.thread_id)
        break
      case 'intent':
        // Waiting UI stays a single “思考中…” bubble until the first
        // content event (errors/explanation) arrives.
        break
      case 'errors':
        setThinking(false)
        upsertCorrection(assistantId, {
          errors: event.errors,
          errorsLoaded: true,
          turnId: event.turn_id,
        })
        break
      case 'minimal':
        if (event.text.trim()) {
          upsertCorrection(assistantId, {
            minimal: { text: event.text, note: event.note },
          })
        } else {
          appendDegraded(assistantId, 'minimal: 改写生成失败')
        }
        break
      case 'fluency':
        if (event.text.trim()) {
          upsertCorrection(assistantId, {
            fluency: { text: event.text, note: event.note },
          })
        } else {
          appendDegraded(assistantId, 'fluency: 改写生成失败')
        }
        break
      case 'rewrite_degraded':
        appendDegraded(assistantId, `${event.stage}: ${event.message}`)
        break
      case 'explanation':
        setThinking(false)
        upsertText(assistantId, { text: event.text })
        break
      case 'error':
        updateItem(assistantId, (item) =>
          item.role === 'assistant'
            ? { ...item, status: 'error', error: event.message }
            : item,
        )
        setThinking(false)
        setError(event.message)
        setBusy(false)
        break
      case 'done':
        updateItem(assistantId, (item) =>
          item.role === 'assistant' && item.status !== 'error'
            ? { ...item, status: 'done' }
            : item,
        )
        setThinking(false)
        setBusy(false)
        break
    }
  }

  async function send(message: string, options: StreamOptions) {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const userId = nextId()
    const assistantId = nextId()
    lastRequestRef.current = { content: message, options }
    setItems((prev) => [...prev, { id: userId, role: 'user', text: message }])
    setContent('')
    setSelected(null)
    setError(null)
    setBusy(true)
    setThinking(true)

    try {
      await streamCorrection(
        message,
        (event) => handleEvent(event, assistantId, controller),
        controller.signal,
        options,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      const message = err instanceof Error ? err.message : '请求失败，请重试'
      setError(message)
      setThinking(false)
    } finally {
      if (!controller.signal.aborted) {
        setBusy(false)
        setThinking(false)
      }
    }
  }

  function handleSend() {
    const message = content.trim()
    if (!message || busy) return
    const options: StreamOptions = { threadId: threadId ?? undefined }
    if (selected) {
      options.intent = 'followup'
      options.turnId = selected.turnId
      options.errorId = selected.errorId
    }
    void send(message, options)
  }

  function handleRetry() {
    const request = lastRequestRef.current
    if (!request || busy) return
    void send(request.content, request.options)
  }

  function handleAsk(turnId: string, errorId: string) {
    setSelected({ turnId, errorId })
    composerRef.current?.focus()
  }

  function handleNewChat() {
    abortRef.current?.abort()
    setItems([])
    setContent('')
    setThreadId(null)
    setSelected(null)
    setError(null)
    setBusy(false)
    setThinking(false)
  }

  return (
    <div className="flex h-screen flex-col bg-[#f8f9fa]">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#dee2e6] bg-white px-4 md:px-6">
        <div>
          <p className="text-sm font-semibold text-[#0a7053]">Echo · 流式纠错</p>
          <p className="text-xs text-[#868e96]">支持最近 10 轮追问</p>
        </div>
        <Button
          variant="outline"
          onClick={handleNewChat}
          className="h-8 border-[#ced4da] bg-white px-3 text-[#343a40] hover:bg-[#f1f3f5]"
        >
          新对话
        </Button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl space-y-4 p-4 md:p-6">
          {items.length === 0 && !busy && (
            <div className="flex min-h-[50vh] items-center justify-center">
              <p className="text-center text-[#868e96]">
                输入英文开始纠错；也可以点击错误卡片追问，或直接继续提问。
              </p>
            </div>
          )}

          {items.map((item) => {
            if (item.role === 'user') {
              return <UserBubble key={item.id} content={item.text} />
            }
            if (item.kind === 'correction') {
              return (
                <ChatCorrectionMessage
                  key={item.id}
                  message={item}
                  onAsk={(errorId) => handleAsk(item.turnId, errorId)}
                />
              )
            }
            return <ChatTextMessage key={item.id} message={item} />
          })}

          {error && (
            <div className="rounded-lg border border-[#ffc9c9] bg-[#fff5f5] p-3 text-sm text-[#c92a2a]">
              <p>{error}</p>
              <Button
                onClick={handleRetry}
                disabled={busy}
                className="mt-2 h-8 bg-[#0ca678] px-3 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
              >
                重试
              </Button>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <ChatComposer
        ref={composerRef}
        value={content}
        onChange={setContent}
        onSend={handleSend}
        busy={busy}
        thinking={thinking}
        selected={selected}
        onClearSelected={() => setSelected(null)}
      />
    </div>
  )
}

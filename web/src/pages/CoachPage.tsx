import { useEffect, useRef, useState } from 'react'

import {
  streamCoach,
  type CoachError,
  type CoachEvent,
  type CoachHistoryMessage,
  type CoachLearning,
  type CoachMode,
  type CoachReport,
  type CoachRewrite,
  type CoachVariant,
} from '@/api/coach'
import RewriteBox from '@/components/correction/RewriteBox'
import UserBubble from '@/components/correction/UserBubble'
import { Button } from '@/components/ui/button'

interface UserItem {
  id: string
  role: 'user'
  text: string
}

interface CoachItem {
  id: string
  role: 'assistant'
  status: 'streaming' | 'done' | 'error'
  startedAt: number
  thinkingMs: number | null
  doneMs: number | null
  mode: CoachMode | null
  reasoning: string
  errors: CoachError[]
  rewrites: Partial<Record<CoachVariant, CoachRewrite>>
  learnings: CoachLearning[]
  answer: string
  error: string | null
}

type ChatItem = UserItem | CoachItem

const MAX_LENGTH = 2000

const REWRITE_META: Record<
  CoachVariant,
  { label: string; icon: string; accent: string }
> = {
  formal: { label: '正式表达', icon: '🎩', accent: 'text-[#7048e8]' },
  casual: { label: '日常表达', icon: '💬', accent: 'text-[#0b7285]' },
  minimal: { label: '最小修正', icon: '✏️', accent: 'text-[#2b8a3e]' },
}

const SEVERITY_STYLE: Record<string, string> = {
  Critical: 'bg-[#fa5252] text-white',
  Major: 'bg-[#f08c00] text-white',
  Minor: 'bg-[#868e96] text-white',
}

function compactReport(report: CoachReport): CoachHistoryMessage {
  if (report.mode === 'answer') {
    return { role: 'assistant', content: report.answer }
  }
  return {
    role: 'assistant',
    content: JSON.stringify({
      mode: report.mode,
      has_errors: report.has_errors,
      errors: report.errors,
      rewrites: report.rewrites,
      learnings: report.learnings,
    }),
  }
}

export default function CoachPage() {
  const [items, setItems] = useState<ChatItem[]>([])
  const [history, setHistory] = useState<CoachHistoryMessage[]>([])
  const [content, setContent] = useState('')
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const idRef = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [items])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  useEffect(() => {
    if (!busy) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 200)
    return () => window.clearInterval(timer)
  }, [busy])

  const nextId = () => {
    idRef.current += 1
    return `c${idRef.current}`
  }

  function updateAssistant(id: string, updater: (item: CoachItem) => CoachItem) {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id && item.role === 'assistant' ? updater(item) : item,
      ),
    )
  }

  function markContent(item: CoachItem, at: number): CoachItem {
    return item.thinkingMs == null
      ? { ...item, thinkingMs: at - item.startedAt }
      : item
  }

  function handleEvent(event: CoachEvent, assistantId: string) {
    const at = Date.now()
    switch (event.kind) {
      case 'report_start':
        updateAssistant(assistantId, (item) =>
          markContent({ ...item, mode: event.mode }, at),
        )
        break
      case 'reasoning':
        updateAssistant(assistantId, (item) => ({
          ...item,
          reasoning: item.reasoning + event.text,
        }))
        break
      case 'error_added':
        updateAssistant(assistantId, (item) => {
          const errors = [...item.errors]
          errors[event.index] = {
            severity: event.severity,
            fragment: event.fragment,
            type: event.type,
            reason: event.reason,
            fix: event.fix,
          }
          return markContent(
            {
              ...item,
              errors: errors.filter((value): value is CoachError => Boolean(value)),
            },
            at,
          )
        })
        break
      case 'rewrite_ready':
        updateAssistant(assistantId, (item) =>
          markContent(
            {
              ...item,
              rewrites: {
                ...item.rewrites,
                [event.variant]: { text: event.text, note: event.note },
              },
            },
            at,
          ),
        )
        break
      case 'learning_added':
        updateAssistant(assistantId, (item) => {
          const learnings = [...item.learnings]
          learnings[event.index] = {
            pattern: event.pattern,
            wrong: event.wrong,
            right: event.right,
            rule: event.rule,
            examples: event.examples,
          }
          return markContent(
            {
              ...item,
              learnings: learnings.filter(
                (value): value is CoachLearning => Boolean(value),
              ),
            },
            at,
          )
        })
        break
      case 'answer_delta':
        updateAssistant(assistantId, (item) =>
          markContent({ ...item, answer: item.answer + event.text }, at),
        )
        break
      case 'error':
        updateAssistant(assistantId, (item) => ({
          ...item,
          status: 'error',
          error: event.message,
          doneMs: at - item.startedAt,
        }))
        setBusy(false)
        break
      case 'done': {
        if (event.report) {
          const report = event.report
          updateAssistant(assistantId, (item) => ({
            ...markContent(item, at),
            status: 'done',
            mode: report.mode,
            errors: report.mode === 'correct' ? report.errors : [],
            rewrites: report.mode === 'correct' ? report.rewrites : {},
            learnings: report.mode === 'correct' ? report.learnings : [],
            answer: report.mode === 'answer' ? report.answer : '',
            doneMs: at - item.startedAt,
          }))
          setHistory((prev) => [...prev, compactReport(report)])
        } else {
          updateAssistant(assistantId, (item) => ({
            ...item,
            status: 'error',
            error: '报告解析失败，请重试',
            doneMs: at - item.startedAt,
          }))
        }
        setBusy(false)
        break
      }
    }
  }

  async function send(message: string) {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const userId = nextId()
    const assistantId = nextId()
    const nextHistory: CoachHistoryMessage[] = [
      ...history,
      { role: 'user', content: message },
    ]
    setHistory(nextHistory)
    setItems((prev) => [
      ...prev,
      { id: userId, role: 'user', text: message },
      {
        id: assistantId,
        role: 'assistant',
        status: 'streaming',
        startedAt: Date.now(),
        thinkingMs: null,
        doneMs: null,
        mode: null,
        reasoning: '',
        errors: [],
        rewrites: {},
        learnings: [],
        answer: '',
        error: null,
      },
    ])
    setContent('')
    setBusy(true)

    try {
      await streamCoach(
        nextHistory,
        (event) => handleEvent(event, assistantId),
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      const message = err instanceof Error ? err.message : '请求失败，请重试'
      updateAssistant(assistantId, (item) => ({
        ...item,
        status: 'error',
        error: message,
        doneMs: Date.now() - item.startedAt,
      }))
    } finally {
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  function handleSend() {
    const message = content.trim()
    if (!message || busy) return
    void send(message)
  }

  function handleNewChat() {
    abortRef.current?.abort()
    setItems([])
    setHistory([])
    setContent('')
    setBusy(false)
  }

  return (
    <div className="flex h-screen flex-col bg-[#f8f9fa]">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#dee2e6] bg-white px-4 md:px-6">
        <div>
          <p className="text-sm font-semibold text-[#0a7053]">Echo · Coach</p>
          <p className="text-xs text-[#868e96]">流式纠错 · 思考过程可见</p>
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
                输入英文获取纠错，或直接提问用法。
              </p>
            </div>
          )}

          {items.map((item) => {
            if (item.role === 'user') {
              return <UserBubble key={item.id} content={item.text} />
            }
            return <CoachMessage key={item.id} message={item} now={now} />
          })}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-[#dee2e6] bg-white px-4 py-3 md:px-8">
        <div className="mx-auto w-full max-w-3xl">
          <div className="flex items-end gap-2">
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter' || event.shiftKey) return
                if (event.nativeEvent.isComposing || event.keyCode === 229) return
                event.preventDefault()
                if (content.trim() && !busy) handleSend()
              }}
              placeholder="输入英文，或提问用法"
              rows={1}
              className="min-h-11 min-w-0 flex-1 resize-none rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
            />
            <Button
              type="button"
              onClick={handleSend}
              disabled={busy || content.trim().length === 0}
              className="h-11 shrink-0 bg-[#0ca678] px-5 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
            >
              {busy ? '分析中…' : '发送'}
            </Button>
          </div>
          <div className="mt-1 flex justify-between text-xs text-[#868e96]">
            <span>Enter 发送，Shift+Enter 换行</span>
            <span className={content.length > MAX_LENGTH ? 'text-[#fa5252]' : ''}>
              {content.length}/{MAX_LENGTH}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function CoachMessage({ message, now }: { message: CoachItem; now: number }) {
  const streaming = message.status === 'streaming'
  const mode = message.mode
  const hasContent =
    message.reasoning ||
    message.answer ||
    message.errors.length > 0 ||
    Object.keys(message.rewrites).length > 0 ||
    message.learnings.length > 0

  const formatSeconds = (ms: number) => `${(ms / 1000).toFixed(1)}s`
  const elapsed = streaming ? now - message.startedAt : message.doneMs
  const timing =
    message.doneMs != null
      ? message.thinkingMs != null
        ? `思考 ${formatSeconds(message.thinkingMs)} · 总耗时 ${formatSeconds(message.doneMs)}`
        : `总耗时 ${formatSeconds(message.doneMs)}`
      : message.thinkingMs != null
        ? `思考 ${formatSeconds(message.thinkingMs)} · 已用时 ${formatSeconds(elapsed ?? 0)}`
        : `已用时 ${formatSeconds(elapsed ?? 0)}`

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-sm font-semibold text-[#343a40]">Coach</span>
          {mode && (
            <span className="rounded bg-[#e6fcf5] px-1.5 py-0.5 text-xs text-[#0a7053]">
              {mode === 'correct' ? '纠错' : '问答'}
            </span>
          )}
          {streaming && <span className="text-xs text-[#868e96]">流式生成中…</span>}
          <span
            data-testid="coach-timing"
            className="ml-auto text-xs text-[#868e96]"
            aria-live="polite"
          >
            {timing}
          </span>
        </div>

        {message.reasoning && (
          <ReasoningPanel
            text={message.reasoning}
            label={
              message.thinkingMs != null
                ? `思考过程 · ${formatSeconds(message.thinkingMs)}`
                : '思考过程'
            }
          />
        )}

        {!hasContent && streaming && (
          <p className="text-sm text-[#868e96]">思考中…</p>
        )}

        {mode === 'answer' && message.answer && (
          <p
            data-testid="coach-answer"
            className="whitespace-pre-wrap text-[#212529]"
          >
            {message.answer}
          </p>
        )}

        {mode === 'correct' && (
          <>
            <div data-testid="coach-errors" className="rounded-lg border border-[#dee2e6] p-3">
              <p className="mb-2 text-sm font-semibold text-[#343a40]">错误分析</p>
              {message.errors.length > 0 ? (
                <div className="space-y-2">
                  {message.errors.map((error, index) => (
                    <div
                      key={`${index}-${error.fragment}`}
                      className="rounded-lg border border-[#dee2e6] border-l-4 border-l-[#fa5252] p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs ${
                            SEVERITY_STYLE[error.severity] ?? SEVERITY_STYLE.Minor
                          }`}
                        >
                          {error.severity}
                        </span>
                        <span className="rounded bg-[#f1f3f5] px-1.5 py-0.5 text-xs text-[#495057]">
                          {error.type}
                        </span>
                        <span className="text-sm font-medium text-[#c92a2a] line-through">
                          {error.fragment}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm text-[#495057]">{error.reason}</p>
                      <p className="mt-1 text-sm font-medium text-[#2b8a3e]">
                        ✅ {error.fix}
                      </p>
                    </div>
                  ))}
                </div>
              ) : streaming ? (
                <p className="text-sm text-[#868e96]">分析中…</p>
              ) : (
                <p className="text-sm text-[#0a7053]">
                  🎉 这段英文写得不错，没有发现需要修正的问题。
                </p>
              )}
            </div>

            <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
              <p className="mb-2 text-sm font-semibold text-[#343a40]">改写</p>
              <div className="space-y-2">
                {(['formal', 'casual', 'minimal'] as CoachVariant[]).map((variant) => {
                  const meta = REWRITE_META[variant]
                  const rewrite = message.rewrites[variant]
                  if (rewrite) {
                    return (
                      <RewriteBox
                        key={variant}
                        label={meta.label}
                        icon={meta.icon}
                        accent={meta.accent}
                        text={rewrite.text}
                        note={rewrite.note ?? ''}
                        testId={`coach-rewrite-${variant}`}
                      />
                    )
                  }
                  if (!streaming) return null
                  return (
                    <RewriteBox
                      key={variant}
                      label={meta.label}
                      icon={meta.icon}
                      accent={meta.accent}
                      loading
                      testId={`coach-rewrite-${variant}`}
                    />
                  )
                })}
              </div>
            </div>

            {message.learnings.length > 0 && (
              <div
                data-testid="coach-learnings"
                className="mt-2 rounded-lg border border-[#dee2e6] p-3"
              >
                <p className="mb-2 text-sm font-semibold text-[#343a40]">学习要点</p>
                <div className="space-y-2">
                  {message.learnings.map((learning, index) => (
                    <div
                      key={`${index}-${learning.pattern}`}
                      className="rounded-lg bg-[#f8f9fa] p-3"
                    >
                      <p className="text-sm font-semibold text-[#0a7053]">
                        {learning.pattern}
                      </p>
                      <p className="mt-1 text-sm text-[#495057]">{learning.rule}</p>
                      <p className="mt-1 text-xs text-[#c92a2a]">❌ {learning.wrong}</p>
                      <p className="text-xs text-[#2b8a3e]">✅ {learning.right}</p>
                      {learning.examples.length > 0 && (
                        <ul className="mt-1 space-y-0.5 text-xs text-[#868e96]">
                          {learning.examples.map((example) => (
                            <li key={example}>{example}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {message.status === 'error' && message.error && (
          <div className="mt-2 rounded-lg border border-[#ffc9c9] bg-[#fff5f5] p-3 text-sm text-[#c92a2a]">
            {message.error}
          </div>
        )}
      </div>
    </div>
  )
}

function ReasoningPanel({ text, label }: { text: string; label: string }) {
  const [open, setOpen] = useState(true)
  const preRef = useRef<HTMLPreElement>(null)
  const pinnedRef = useRef(true)

  useEffect(() => {
    const el = preRef.current
    if (!el || !open || !pinnedRef.current) return
    el.scrollTop = el.scrollHeight
  }, [text, open])

  return (
    <details
      data-testid="coach-reasoning"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className="mb-2 rounded-lg border border-[#e9ecef] bg-[#f8f9fa]"
    >
      <summary className="cursor-pointer px-3 py-2 text-xs text-[#868e96]">
        {label}
      </summary>
      <pre
        ref={preRef}
        data-testid="coach-reasoning-content"
        onScroll={(event) => {
          const el = event.currentTarget
          pinnedRef.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 24
        }}
        className="max-h-48 overflow-y-auto whitespace-pre-wrap px-3 pb-2 text-xs leading-relaxed text-[#868e96]"
      >
        {text}
      </pre>
    </details>
  )
}

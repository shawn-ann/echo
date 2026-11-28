import { useEffect, useRef, useState } from 'react'

import {
  fetchCorrections,
  normalizeStoredReport,
  streamCorrection,
  type CorrectionEvent,
  type StoredCorrection,
} from '@/api/correction'
import type { CoachError, CoachRewrite, CoachVariant } from '@/api/coach'
import RewriteBox from '@/components/correction/RewriteBox'
import TimingText from '@/components/correction/TimingText'
import UserBubble from '@/components/correction/UserBubble'
import { Button } from '@/components/ui/button'

const MAX_LENGTH = 2000

const REWRITE_META: Record<
  CoachVariant,
  { label: string; icon: string; accent: string }
> = {
  formal: { label: '正式表达', icon: '🎩', accent: 'text-[#7048e8]' },
  casual: { label: '日常表达', icon: '💬', accent: 'text-[#0b7285]' },
  minimal: { label: '最小修正', icon: '✏️', accent: 'text-[#2b8a3e]' },
}

function dayKey(iso: string) {
  const date = new Date(iso)
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`
}

function formatDay(iso: string) {
  return new Date(iso).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  })
}

const SEVERITY_STYLE: Record<string, string> = {
  Critical: 'bg-[#fa5252] text-white',
  Major: 'bg-[#f08c00] text-white',
  Minor: 'bg-[#868e96] text-white',
}

interface ResultState {
  id: string
  source: string
  createdAt: string
  status: 'streaming' | 'done' | 'error'
  phase: 'thinking' | 'correct'
  reasoning: string
  reasoningOpen: boolean
  errors: CoachError[]
  rewrites: Partial<Record<CoachVariant, CoachRewrite>>
  startedAt: number
  thinkingMs: number | null
  doneMs: number | null
  error: string | null
}

function fromStored(record: StoredCorrection): ResultState {
  const report = normalizeStoredReport(record.report)
  return {
    id: record.id,
    source: record.source_text,
    createdAt: record.created_at,
    status: 'done',
    phase: 'correct',
    reasoning: '',
    reasoningOpen: false,
    errors: report.errors,
    rewrites: report.rewrites,
    startedAt: 0,
    thinkingMs: null,
    doneMs: record.duration_ms,
    error: null,
  }
}

export default function CorrectionStreamPage() {
  const [content, setContent] = useState('')
  const [items, setItems] = useState<ResultState[]>([])
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [historyError, setHistoryError] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const idRef = useRef(0)
  const activeIdRef = useRef<string | null>(null)
  const pinnedRef = useRef(true)
  const skipScrollRef = useRef(false)
  const initialScrolledRef = useRef(false)
  const loadingOlderRef = useRef(false)

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchCorrections()
      .then((page) => {
        if (cancelled) return
        const history = page.corrections.map(fromStored).reverse()
        setItems((prev) => {
          const existing = new Set(prev.map((item) => item.id))
          return [...history.filter((item) => !existing.has(item.id)), ...prev]
        })
        setNextCursor(page.next_cursor)
        setHasMore(page.has_more)
      })
      .catch(() => {
        if (!cancelled) setHistoryError(true)
      })
      .finally(() => {
        if (!cancelled) setInitialLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (skipScrollRef.current) {
      skipScrollRef.current = false
      return
    }
    if (!initialScrolledRef.current || pinnedRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'auto' })
      initialScrolledRef.current = true
    }
  }, [items])

  useEffect(() => {
    if (!busy) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 200)
    return () => window.clearInterval(timer)
  }, [busy])

  const nextId = () => {
    idRef.current += 1
    return `local-${idRef.current}`
  }

  function patchItem(id: string, updater: (item: ResultState) => ResultState) {
    setItems((prev) => prev.map((item) => (item.id === id ? updater(item) : item)))
  }

  function markContent(id: string, at: number) {
    patchItem(id, (item) =>
      item.thinkingMs == null
        ? { ...item, thinkingMs: at - item.startedAt }
        : item,
    )
  }

  function handleEvent(event: CorrectionEvent) {
    const id = activeIdRef.current
    if (!id) return
    const at = Date.now()
    switch (event.kind) {
      case 'report_start':
        markContent(id, at)
        patchItem(id, (item) => ({ ...item, phase: 'correct' }))
        break
      case 'reasoning':
        patchItem(id, (item) => ({
          ...item,
          reasoning: item.reasoning + event.text,
        }))
        break
      case 'error_added':
        markContent(id, at)
        patchItem(id, (item) => {
          const errors = [...item.errors]
          errors[event.index] = {
            severity: event.severity,
            fragment: event.fragment,
            type: event.type,
            reason: event.reason,
            fix: event.fix,
          }
          return {
            ...item,
            phase: 'correct',
            reasoningOpen: event.index === 0 ? false : item.reasoningOpen,
            errors: errors.filter((value): value is CoachError => Boolean(value)),
          }
        })
        break
      case 'rewrite_ready':
        markContent(id, at)
        patchItem(id, (item) => ({
          ...item,
          phase: 'correct',
          rewrites: {
            ...item.rewrites,
            [event.variant]: { text: event.text, note: event.note },
          },
        }))
        break
      case 'done':
        patchItem(id, (item) => {
          if (!event.report) {
            return {
              ...item,
              status: 'error',
              error: '报告解析失败，请重试',
              doneMs: at - item.startedAt,
            }
          }
          return {
            ...item,
            status: 'done',
            phase: 'correct',
            errors: event.report.errors,
            rewrites: event.report.rewrites,
            thinkingMs: item.thinkingMs ?? at - item.startedAt,
            doneMs: at - item.startedAt,
          }
        })
        setBusy(false)
        break
      case 'error':
        patchItem(id, (item) => ({
          ...item,
          status: 'error',
          error: event.message,
          doneMs: at - item.startedAt,
        }))
        setBusy(false)
        break
    }
  }

  async function loadOlder() {
    if (
      loadingOlderRef.current ||
      initialLoading ||
      !hasMore ||
      !nextCursor
    ) {
      return
    }
    loadingOlderRef.current = true
    setLoadingOlder(true)
    const el = scrollRef.current
    const previousHeight = el?.scrollHeight ?? 0
    try {
      const page = await fetchCorrections(nextCursor)
      const older = page.corrections.map(fromStored).reverse()
      skipScrollRef.current = true
      setItems((prev) => [...older, ...prev])
      setNextCursor(page.next_cursor)
      setHasMore(page.has_more)
      requestAnimationFrame(() => {
        if (el) el.scrollTop += el.scrollHeight - previousHeight
      })
    } catch {
      setHistoryError(true)
    } finally {
      loadingOlderRef.current = false
      setLoadingOlder(false)
    }
  }

  async function send() {
    const message = content.trim()
    if (!message || busy) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const startedAt = Date.now()
    const id = nextId()
    activeIdRef.current = id
    pinnedRef.current = true
    setItems((prev) => [
      ...prev,
      {
        id,
        source: message,
        createdAt: new Date().toISOString(),
        status: 'streaming',
        phase: 'thinking',
        reasoning: '',
        reasoningOpen: true,
        errors: [],
        rewrites: {},
        startedAt,
        thinkingMs: null,
        doneMs: null,
        error: null,
      },
    ])
    setContent('')
    setBusy(true)

    try {
      await streamCorrection(message, handleEvent, controller.signal)
    } catch (err) {
      if (controller.signal.aborted) return
      const text = err instanceof Error ? err.message : '请求失败，请重试'
      patchItem(id, (item) => ({ ...item, status: 'error', error: text }))
    } finally {
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col bg-[#f8f9fa]">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        onScroll={(event) => {
          const el = event.currentTarget
          pinnedRef.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 100
          if (el.scrollTop < 40) void loadOlder()
        }}
      >
        <div className="mx-auto w-full max-w-3xl space-y-4 p-4 md:p-6">
          {initialLoading && items.length === 0 && (
            <div className="flex min-h-[50vh] items-center justify-center">
              <p className="text-center text-[#868e96]">加载历史…</p>
            </div>
          )}
          {loadingOlder && (
            <p className="text-center text-xs text-[#868e96]">加载更早记录…</p>
          )}
          {items.length === 0 && !busy && !historyError && !initialLoading && (
            <div className="flex min-h-[50vh] items-center justify-center">
              <p className="text-center text-[#868e96]">
                输入一段英文，获取错误分析和三版改写。
              </p>
            </div>
          )}
          {items.length === 0 && historyError && (
            <div className="flex min-h-[50vh] items-center justify-center">
              <p className="text-center text-[#868e96]">
                历史加载失败，可以直接开始新的纠错。
              </p>
            </div>
          )}

          {items.map((item, index) => {
            const showDayHeader =
              index === 0 || dayKey(items[index - 1].createdAt) !== dayKey(item.createdAt)
            return (
            <div key={item.id} className="space-y-3">
              {showDayHeader && (
                <div className="sticky top-0 z-10 -mx-1 bg-[#f8f9fa]/95 px-1 py-1 text-xs font-medium text-[#868e96]">
                  {formatDay(item.createdAt)}
                </div>
              )}
              <UserBubble content={item.source} />
              <div className="flex justify-start">
                <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-[#343a40]">
                      纠错结果
                    </span>
                    <TimingText
                      startedAt={item.startedAt}
                      thinkingMs={item.reasoning ? item.thinkingMs : null}
                      doneMs={item.doneMs}
                      now={now}
                      testId="correction-timing"
                    />
                  </div>

                  {item.phase === 'thinking' ? (
                    <ThinkingStage
                      reasoning={item.reasoning}
                      open={item.reasoningOpen}
                      onOpenChange={(open) =>
                        patchItem(item.id, (current) => ({
                          ...current,
                          reasoningOpen: open,
                        }))
                      }
                    />
                  ) : (
                    <>
                      {item.reasoning && (
                        <ReasoningPanel
                          text={item.reasoning}
                          open={item.reasoningOpen}
                          onOpenChange={(open) =>
                            patchItem(item.id, (current) => ({
                              ...current,
                              reasoningOpen: open,
                            }))
                          }
                        />
                      )}

                      <div className="rounded-lg border border-[#dee2e6] p-3">
                        <p className="mb-2 text-sm font-semibold text-[#343a40]">
                          错误分析
                        </p>
                        {item.errors.length > 0 ? (
                          <div className="space-y-2">
                            {item.errors.map((error, index) => (
                              <div
                                key={`${item.id}-${index}-${error.fragment}`}
                                className="rounded-lg border border-[#dee2e6] border-l-4 border-l-[#fa5252] p-3"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <span
                                    className={`rounded px-1.5 py-0.5 text-xs ${
                                      SEVERITY_STYLE[error.severity] ??
                                      SEVERITY_STYLE.Minor
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
                                <p className="mt-1.5 text-sm text-[#495057]">
                                  {error.reason}
                                </p>
                                <p className="mt-1 text-sm font-medium text-[#2b8a3e]">
                                  ✅ {error.fix}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : item.status === 'streaming' ? (
                          <p className="text-sm text-[#868e96]">分析中…</p>
                        ) : (
                          <p className="text-sm text-[#0a7053]">
                            🎉 这段英文写得不错，没有发现需要修正的问题。
                          </p>
                        )}
                      </div>

                      <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
                        <p className="mb-2 text-sm font-semibold text-[#343a40]">
                          改写
                        </p>
                        <div className="space-y-2">
                          {(['formal', 'casual', 'minimal'] as CoachVariant[]).map(
                            (variant) => {
                              const meta = REWRITE_META[variant]
                              const rewrite = item.rewrites[variant]
                              if (rewrite) {
                                return (
                                  <RewriteBox
                                    key={variant}
                                    label={meta.label}
                                    icon={meta.icon}
                                    accent={meta.accent}
                                    text={rewrite.text}
                                    note={rewrite.note ?? ''}
                                    testId={`correction-rewrite-${variant}`}
                                  />
                                )
                              }
                              if (item.status !== 'streaming') return null
                              return (
                                <RewriteBox
                                  key={variant}
                                  label={meta.label}
                                  icon={meta.icon}
                                  accent={meta.accent}
                                  loading
                                  testId={`correction-rewrite-${variant}`}
                                />
                              )
                            },
                          )}
                        </div>
                      </div>
                    </>
                  )}

                  {item.error && (
                    <div className="mt-2 rounded-lg border border-[#ffc9c9] bg-[#fff5f5] p-3 text-sm text-[#c92a2a]">
                      {item.error}
                    </div>
                  )}
                </div>
              </div>
            </div>
            )
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
                if (content.trim() && !busy) void send()
              }}
              placeholder="输入英文，获取纠错和改写"
              rows={1}
              className="min-h-11 min-w-0 flex-1 resize-none rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
            />
            <Button
              type="button"
              onClick={() => void send()}
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

function ThinkingStage({
  reasoning,
  open,
  onOpenChange,
}: {
  reasoning: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <>
      {reasoning && (
        <ReasoningPanel text={reasoning} open={open} onOpenChange={onOpenChange} />
      )}
      <div
        data-testid="correction-thinking"
        className="rounded-lg border border-[#dee2e6] bg-white p-3"
      >
        <p className="text-sm text-[#868e96]">正在分析…</p>
        <div className="mt-3 space-y-2">
          <div className="h-3 w-4/5 animate-pulse rounded bg-[#e9ecef]" />
          <div className="h-3 w-3/5 animate-pulse rounded bg-[#e9ecef]" />
        </div>
      </div>
    </>
  )
}

function ReasoningPanel({
  text,
  open,
  onOpenChange,
}: {
  text: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const preRef = useRef<HTMLPreElement>(null)
  const pinnedRef = useRef(true)

  useEffect(() => {
    const el = preRef.current
    if (!el || !open || !pinnedRef.current) return
    el.scrollTop = el.scrollHeight
  }, [text, open])

  return (
    <details
      data-testid="correction-reasoning"
      open={open}
      className="mb-2 rounded-lg border border-[#e9ecef] bg-[#f8f9fa]"
    >
      <summary
        className="cursor-pointer px-3 py-2 text-xs text-[#868e96]"
        onClick={(event) => {
          event.preventDefault()
          onOpenChange(!open)
        }}
      >
        思考过程
      </summary>
      <pre
        ref={preRef}
        onScroll={(event) => {
          const el = event.currentTarget
          pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
        }}
        className="max-h-48 overflow-y-auto whitespace-pre-wrap px-3 pb-2 text-xs leading-relaxed text-[#868e96]"
      >
        {text}
      </pre>
    </details>
  )
}

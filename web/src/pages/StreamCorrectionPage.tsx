import { useEffect, useRef, useState } from 'react'

import {
  streamCorrection,
  type ChatError,
  type ChatEvent,
  type ChatRewrite,
} from '@/api/chat'
import ErrorCard from '@/components/correction/ErrorCard'
import StreamRewriteCard from '@/components/correction/StreamRewriteCard'
import { Button } from '@/components/ui/button'

const MAX_LENGTH = 2000

type Phase = 'idle' | 'locating' | 'rewriting' | 'followup' | 'done' | 'error'

interface Report {
  turnId: string
  text: string
  errors: ChatError[]
}

interface Explanation {
  text: string
  turnId: string | null
  errorId: string | null
}

export default function StreamCorrectionPage() {
  const [text, setText] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [threadId, setThreadId] = useState<string | null>(null)
  const [reports, setReports] = useState<Report[]>([])
  const [minimal, setMinimal] = useState<ChatRewrite | null>(null)
  const [fluency, setFluency] = useState<ChatRewrite | null>(null)
  const [degraded, setDegraded] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [followupText, setFollowupText] = useState('')
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null)
  const [selectedErrorId, setSelectedErrorId] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const terminalErrorRef = useRef(false)
  const lastSubmittedRef = useRef('')
  const followupRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const busy = phase === 'locating' || phase === 'rewriting' || phase === 'followup'
  const over = text.length > MAX_LENGTH
  const disabled = busy || text.trim().length === 0 || over
  const followupDisabled = busy || !threadId || followupText.trim().length === 0

  function handleEvent(event: ChatEvent, controller: AbortController) {
    if (controller.signal.aborted) return
    switch (event.type) {
      case 'thread':
        setThreadId(event.thread_id)
        break
      case 'intent':
        if (event.intent === 'followup') setPhase('followup')
        break
      case 'errors':
        setReports((prev) =>
          [
            ...prev,
            {
              turnId: event.turn_id,
              text: lastSubmittedRef.current,
              errors: event.errors,
            },
          ].slice(-10),
        )
        setPhase('rewriting')
        break
      case 'minimal':
        if (event.text.trim()) {
          setMinimal({ text: event.text, note: event.note })
        } else {
          setDegraded((prev) => [...prev, 'minimal: 改写生成失败'])
        }
        break
      case 'fluency':
        if (event.text.trim()) {
          setFluency({ text: event.text, note: event.note })
        } else {
          setDegraded((prev) => [...prev, 'fluency: 改写生成失败'])
        }
        break
      case 'rewrite_degraded':
        setDegraded((prev) => [...prev, `${event.stage}: ${event.message}`])
        break
      case 'explanation':
        setExplanation({
          text: event.text,
          turnId: event.turn_id,
          errorId: event.error_id,
        })
        setPhase('done')
        break
      case 'error':
        terminalErrorRef.current = true
        setError(event.message)
        setPhase('error')
        break
      case 'done':
        if (!terminalErrorRef.current) setPhase('done')
        break
    }
  }

  async function handleStart() {
    const content = text.trim()
    if (!content || disabled) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    terminalErrorRef.current = false
    lastSubmittedRef.current = content
    setPhase('locating')
    setMinimal(null)
    setFluency(null)
    setDegraded([])
    setError(null)
    setExplanation(null)
    setSelectedTurnId(null)
    setSelectedErrorId(null)

    try {
      await streamCorrection(
        content,
        (event) => handleEvent(event, controller),
        controller.signal,
        { threadId: threadId ?? undefined, intent: 'correct' },
      )
    } catch (err) {
      if (controller.signal.aborted) return
      terminalErrorRef.current = true
      setError(err instanceof Error ? err.message : '请求失败，请重试')
      setPhase('error')
    }
  }

  async function handleFollowup() {
    const question = followupText.trim()
    if (!question || !threadId || busy) return

    const turnId = selectedTurnId
    const errorId = selectedErrorId
    setSelectedTurnId(null)
    setSelectedErrorId(null)
    setFollowupText('')

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    terminalErrorRef.current = false
    setError(null)
    setExplanation(null)
    setPhase('followup')

    try {
      await streamCorrection(
        question,
        (event) => handleEvent(event, controller),
        controller.signal,
        {
          threadId,
          intent: 'followup',
          turnId: turnId ?? undefined,
          errorId: errorId ?? undefined,
        },
      )
    } catch (err) {
      if (controller.signal.aborted) return
      terminalErrorRef.current = true
      setError(err instanceof Error ? err.message : '请求失败，请重试')
      setPhase('error')
    }
  }

  function handleAsk(turnId: string, errorId: string) {
    setSelectedTurnId(turnId)
    setSelectedErrorId(errorId)
    followupRef.current?.focus()
  }

  return (
    <div className="min-h-screen bg-[#f8f9fa] p-4 md:p-8">
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold text-[#212529]">流式纠错实验</h1>
          <p className="text-sm text-[#868c96]">先出错误列表，再出两版改写。支持追问最近 10 轮。</p>
        </header>

        <div className="space-y-2 rounded-xl border border-[#dee2e6] bg-white p-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入英文，开始流式纠错"
            rows={4}
            className="w-full resize-y rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
          />
          <div className="flex items-center justify-between gap-3">
            <span className={`text-sm ${over ? 'text-[#fa5252]' : 'text-[#868c96]'}`}>
              {over ? '请将文本缩短至 2000 字符以内再提交' : `${text.length}/${MAX_LENGTH}`}
            </span>
            <Button
              onClick={handleStart}
              disabled={disabled}
              className="h-10 bg-[#0ca678] px-5 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
            >
              {busy ? '分析中…' : '开始'}
            </Button>
          </div>
        </div>

        {phase === 'locating' && (
          <p className="text-center text-sm text-[#868c96]">正在分析…</p>
        )}

        {phase !== 'error' &&
          reports.map((report) => (
            <div
              key={report.turnId}
              data-testid="stream-errors"
              className="rounded-xl border border-[#dee2e6] bg-white p-3"
            >
              <div className="mb-2">
                <p className="text-sm font-semibold text-[#343a40]">
                  错误分析
                  <span className="ml-2 text-xs font-normal text-[#868c96]">{report.turnId}</span>
                </p>
                <p className="truncate text-xs text-[#868c96]">{report.text}</p>
              </div>
              {report.errors.length > 0 ? (
                <div className="space-y-2">
                  {report.errors.map((item, index) => (
                    <ErrorCard
                      key={`${index}-${item.error_id}-${item.fragment}`}
                      error={item}
                      onAsk={() => handleAsk(report.turnId, item.error_id)}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-[#0a7053]">未检测到语法错误</p>
              )}
            </div>
          ))}

        {minimal && (
          <StreamRewriteCard
            title="最小修正"
            text={minimal.text}
            note={minimal.note}
            testId="stream-minimal"
          />
        )}

        {fluency && (
          <StreamRewriteCard
            title="地道表达"
            text={fluency.text}
            note={fluency.note}
            testId="stream-fluency"
          />
        )}

        {degraded.length > 0 && (
          <div className="rounded-lg border border-[#ffd43b] bg-[#fff9db] p-3 text-sm text-[#8a6d00]">
            {degraded.map((item) => (
              <p key={item}>部分改写生成失败：{item}</p>
            ))}
          </div>
        )}

        {reports.length > 0 && (
          <div className="space-y-2 rounded-xl border border-[#dee2e6] bg-white p-3">
            <p className="text-sm font-semibold text-[#343a40]">追问</p>
            <div className="flex flex-col gap-2 md:flex-row">
              <input
                ref={followupRef}
                value={followupText}
                onChange={(e) => setFollowupText(e.target.value)}
                placeholder="输入追问，例如：为什么这么改？"
                className="min-w-0 flex-1 rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3 py-2 text-sm focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
              />
              <Button
                onClick={handleFollowup}
                disabled={followupDisabled}
                className="h-9 bg-[#0ca678] px-4 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
              >
                {phase === 'followup' ? '解释中…' : '发送追问'}
              </Button>
            </div>
            {selectedTurnId && selectedErrorId && (
              <p className="text-xs text-[#868e96]">
                当前追问：{selectedTurnId}:{selectedErrorId}
              </p>
            )}
          </div>
        )}

        {explanation && (
          <div
            data-testid="stream-explanation"
            className="rounded-xl border border-[#dee2e6] bg-white p-3"
          >
            <p className="mb-1 text-sm font-semibold text-[#343a40]">
              解释
              {explanation.turnId && explanation.errorId && (
                <span className="ml-2 text-xs font-normal text-[#868c96]">
                  {explanation.turnId}:{explanation.errorId}
                </span>
              )}
            </p>
            <p className="text-sm whitespace-pre-wrap text-[#212529]">{explanation.text}</p>
          </div>
        )}

        {error && (
          <div className="space-y-2 rounded-lg border border-[#ffc9c9] bg-[#fff5f5] p-3 text-sm text-[#c92a2a]">
            <p>{error}</p>
            <Button
              onClick={handleStart}
              disabled={text.trim().length === 0 || over}
              className="h-8 bg-[#0ca678] px-3 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
            >
              重试
            </Button>
          </div>
        )}

        {phase === 'done' && <p className="text-center text-xs text-[#868c96]">完成</p>}
      </div>
    </div>
  )
}

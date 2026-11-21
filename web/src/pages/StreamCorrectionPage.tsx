import { useEffect, useRef, useState } from 'react'

import { streamCorrection, type ChatError, type ChatRewrite } from '@/api/chat'
import ErrorCard from '@/components/correction/ErrorCard'
import StreamRewriteCard from '@/components/correction/StreamRewriteCard'
import { Button } from '@/components/ui/button'

const MAX_LENGTH = 2000

type Phase = 'idle' | 'locating' | 'rewriting' | 'done' | 'error'

export default function StreamCorrectionPage() {
  const [text, setText] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [started, setStarted] = useState(false)
  const [errors, setErrors] = useState<ChatError[]>([])
  const [minimal, setMinimal] = useState<ChatRewrite | null>(null)
  const [fluency, setFluency] = useState<ChatRewrite | null>(null)
  const [degraded, setDegraded] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const terminalErrorRef = useRef(false)

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const busy = phase === 'locating' || phase === 'rewriting'
  const over = text.length > MAX_LENGTH
  const disabled = busy || text.trim().length === 0 || over

  async function handleStart() {
    const content = text.trim()
    if (!content || disabled) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    terminalErrorRef.current = false
    setStarted(true)
    setPhase('locating')
    setErrors([])
    setMinimal(null)
    setFluency(null)
    setDegraded([])
    setError(null)

    try {
      await streamCorrection(
        content,
        (event) => {
          if (controller.signal.aborted) return
          switch (event.type) {
            case 'errors':
              setErrors(event.errors)
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
            case 'error':
              terminalErrorRef.current = true
              setError(event.message)
              setPhase('error')
              break
            case 'done':
              if (!terminalErrorRef.current) setPhase('done')
              break
          }
        },
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      terminalErrorRef.current = true
      setError(err instanceof Error ? err.message : '请求失败，请重试')
      setPhase('error')
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f9fa] p-4 md:p-8">
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold text-[#212529]">流式纠错实验</h1>
          <p className="text-sm text-[#868c96]">先出错误列表，再出两版改写。刷新即丢失，仅用于 MVP 联调。</p>
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

        {started && (
          <div data-testid="stream-errors" className="rounded-xl border border-[#dee2e6] bg-white p-3">
            <p className="mb-2 text-sm font-semibold text-[#343a40]">错误分析</p>
            {errors.length > 0 ? (
              <div className="space-y-2">
                {errors.map((item, index) => (
                  <ErrorCard key={`${index}-${item.fragment}`} error={item} />
                ))}
              </div>
            ) : phase === 'rewriting' || phase === 'done' ? (
              <p className="text-sm text-[#0a7053]">未检测到语法错误</p>
            ) : null}
          </div>
        )}

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

        {error && (
          <div className="rounded-lg border border-[#ffc9c9] bg-[#fff5f5] p-3 text-sm text-[#c92a2a]">
            {error}
          </div>
        )}

        {phase === 'done' && <p className="text-center text-xs text-[#868c96]">完成</p>}
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'

interface Props {
  label: string
  icon: string
  accent: string
  text?: string
  note?: string
  loading?: boolean
  emptyMessage?: string
  testId?: string
}

export default function RewriteBox({
  label,
  icon,
  accent,
  text = '',
  note = '',
  loading = false,
  emptyMessage,
  testId,
}: Props) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    return () => {
      window.clearTimeout(timerRef.current)
    }
  }, [])

  async function copy() {
    if (!navigator.clipboard) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.clearTimeout(timerRef.current)
      timerRef.current = window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 复制失败：静默，不打断用户
    }
  }

  const showEmpty = !loading && !!emptyMessage

  return (
    <div data-testid={testId}>
      <p className={`text-sm font-semibold ${accent}`}>
        {icon} {label}
      </p>
      <div className="relative mt-1 rounded-lg border border-dashed border-[#0ca678] bg-[#f0fdfa] p-3 pr-10">
        {loading ? (
          <div data-testid={testId ? `${testId}-loading` : undefined} className="space-y-2 py-0.5">
            <div className="h-3 w-4/5 animate-pulse rounded bg-[#d3f9ee]" />
            <div className="h-3 w-3/5 animate-pulse rounded bg-[#d3f9ee]" />
          </div>
        ) : showEmpty ? (
          <p className="text-sm text-[#868e96]">{emptyMessage}</p>
        ) : (
          <>
            <button
              type="button"
              onClick={copy}
              aria-label={`复制${label}`}
              className="absolute right-1.5 top-1.5 flex size-9 items-center justify-center rounded-md text-[#868e96] hover:border hover:border-[#0ca678] hover:text-[#0ca678]"
            >
              {copied ? <span className="text-[#2b8a3e]">✓</span> : <span>📋</span>}
            </button>
            <p className="whitespace-pre-wrap text-[#212529]">{text}</p>
          </>
        )}
      </div>
      {!loading && !showEmpty && note && (
        <p className="mt-1 text-xs text-[#868e96]">{note}</p>
      )}
    </div>
  )
}

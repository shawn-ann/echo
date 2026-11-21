import { useEffect, useRef, useState } from 'react'

interface Props {
  title: string
  text: string
  note: string
  testId: string
}

export default function StreamRewriteCard({ title, text, note, testId }: Props) {
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

  return (
    <div data-testid={testId} className="rounded-lg border border-[#dee2e6] bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-[#343a40]">{title}</p>
        <button
          type="button"
          onClick={copy}
          aria-label={`复制${title}`}
          className="flex size-8 items-center justify-center rounded-md text-[#868e96] hover:border hover:border-[#0ca678] hover:text-[#0ca678]"
        >
          {copied ? <span className="text-[#2b8a3e]">✓</span> : <span>📋</span>}
        </button>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-[#212529]">{text}</p>
      <p className="mt-1 text-xs text-[#868e96]">{note}</p>
    </div>
  )
}

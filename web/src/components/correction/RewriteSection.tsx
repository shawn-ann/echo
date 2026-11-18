import { useEffect, useRef, useState } from 'react'

import type { RewriteOption, RewriteSection as RewriteSectionType } from '@/api/messages'

function RewriteBox({
  label,
  icon,
  option,
  accent,
}: {
  label: string
  icon: string
  option: RewriteOption
  accent: string
}) {
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
      await navigator.clipboard.writeText(option.text)
      setCopied(true)
      window.clearTimeout(timerRef.current)
      timerRef.current = window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 复制失败：静默，不打断用户
    }
  }

  return (
    <div>
      <p className={`text-sm font-semibold ${accent}`}>
        {icon} {label}
      </p>
      <div className="relative mt-1 rounded-lg border border-dashed border-[#0ca678] bg-[#f0fdfa] p-3 pr-10">
        <button
          type="button"
          onClick={copy}
          aria-label={`复制${label}`}
          className="absolute right-1.5 top-1.5 flex size-9 items-center justify-center rounded-md text-[#868e96] hover:border hover:border-[#0ca678] hover:text-[#0ca678]"
        >
          {copied ? <span className="text-[#2b8a3e]">✓</span> : <span>📋</span>}
        </button>
        <p className="whitespace-pre-wrap text-[#212529]">{option.text}</p>
      </div>
      <p className="mt-1 text-xs text-[#868e96]">{option.note}</p>
    </div>
  )
}

export default function RewriteSection({
  rewrite,
  show = 'both',
}: {
  rewrite: RewriteSectionType
  show?: 'both' | 'natural-only'
}) {
  return (
    <div className="space-y-2">
      {show === 'both' && (
        <RewriteBox label="最小修正" icon="✏️" option={rewrite.minimal} accent="text-[#2b8a3e]" />
      )}
      <RewriteBox label="地道表达" icon="✨" option={rewrite.natural} accent="text-[#7048e8]" />
    </div>
  )
}

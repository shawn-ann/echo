import { useState } from 'react'

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

  async function copy() {
    await navigator.clipboard.writeText(option.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="relative rounded-lg border border-dashed border-[#0ca678] bg-[#f0fdfa] p-3 pr-10">
      <button
        type="button"
        onClick={copy}
        aria-label={`复制${label}`}
        className="absolute right-1.5 top-1.5 flex size-9 items-center justify-center rounded-md text-[#868e96] hover:border hover:border-[#0ca678] hover:text-[#0ca678]"
      >
        {copied ? <span className="text-[#2b8a3e]">✓</span> : <span>📋</span>}
      </button>
      <p className={`text-sm font-semibold ${accent}`}>
        {icon} {label}
      </p>
      <p className="mt-1 whitespace-pre-wrap text-[#212529]">{option.text}</p>
      <p className="mt-1 text-xs text-[#868e96]">{option.explanation}</p>
    </div>
  )
}

export default function RewriteSection({ rewrite }: { rewrite: RewriteSectionType }) {
  return (
    <div className="space-y-2">
      <RewriteBox label="最小修正" icon="✏️" option={rewrite.minimal} accent="text-[#2b8a3e]" />
      <RewriteBox label="地道表达" icon="✨" option={rewrite.natural} accent="text-[#7048e8]" />
    </div>
  )
}

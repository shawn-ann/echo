import type { ErrorBlock } from '@/api/messages'

const CATEGORY_LABEL: Record<string, string> = {
  grammar: '语法',
  collocation: '搭配',
  chinglish: '中式英语',
  style: '风格与语气',
}

export default function ErrorCard({ error }: { error: ErrorBlock }) {
  const isChinglish = error.category === 'chinglish'
  const accent = isChinglish
    ? 'border-l-[#f76707]'
    : 'border-l-[#fa5252]'
  return (
    <div className={`rounded-lg border border-[#dee2e6] border-l-4 bg-white p-3 ${accent}`}>
      <div className="flex items-center gap-2">
        <span
          className={`rounded px-1.5 py-0.5 text-xs text-white ${isChinglish ? 'bg-[#f76707]' : 'bg-[#fa5252]'}`}
        >
          {CATEGORY_LABEL[error.category] ?? error.category}
        </span>
        <span className="text-sm font-medium text-[#c92a2a] line-through">
          {error.fragment}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-[#495057]">{error.explanation}</p>
      <p className="mt-1 text-sm font-medium text-[#2b8a3e]">✅ {error.correction}</p>
    </div>
  )
}

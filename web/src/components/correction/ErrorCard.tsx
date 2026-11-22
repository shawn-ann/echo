import type { ErrorBlock } from '@/api/messages'

interface Props {
  error: ErrorBlock
  onAsk?: () => void
}

export default function ErrorCard({ error, onAsk }: Props) {
  const isDeletion = error.correction.trim() === ''

  return (
    <div className="rounded-lg border border-[#dee2e6] border-l-4 border-l-[#fa5252] bg-white p-3">
      <div className="flex items-center gap-2">
        <span className="rounded bg-[#fa5252] px-1.5 py-0.5 text-xs text-white">
          {error.category}
        </span>
        <span className="text-sm font-medium text-[#c92a2a] line-through">
          {error.fragment}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-[#495057]">{error.explanation}</p>
      <div className="mt-1">
        {isDeletion ? (
          <p className="text-sm font-medium text-[#868e96]">🗑️ 建议删除</p>
        ) : (
          <p className="text-sm font-medium text-[#2b8a3e]">✅ {error.correction}</p>
        )}
      </div>
      {onAsk && (
        <button
          type="button"
          onClick={onAsk}
          className="mt-2 rounded-md border border-[#ced4da] bg-white px-2.5 py-1 text-xs text-[#495057] hover:bg-[#f1f3f5]"
        >
          追问这条
        </button>
      )}
    </div>
  )
}

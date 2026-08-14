import type { ErrorBlock } from '@/api/messages'

export default function ErrorCard({ error }: { error: ErrorBlock }) {
  return (
    <div className="rounded-lg border border-[#dee2e6] border-l-4 border-l-[#fa5252] bg-white p-3">
      <div className="flex items-center gap-2">
        <span className="rounded bg-[#fa5252] px-1.5 py-0.5 text-xs text-white">
          {error.error_type}
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

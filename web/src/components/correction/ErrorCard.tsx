import type { ErrorBlock } from '@/api/messages'
import { Button } from '@/components/ui/button'

type SaveState = 'idle' | 'loading' | 'done'

interface Props {
  error: ErrorBlock
  state: SaveState
  onSave?: () => void
}

export default function ErrorCard({ error, state, onSave }: Props) {
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
      <div className="mt-1 flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-[#2b8a3e]">✅ {error.correction}</p>
        {onSave && (
          <Button
            variant="ghost"
            size="xs"
            disabled={state !== 'idle'}
            onClick={onSave}
            className="shrink-0 text-[#0ca678] hover:bg-[#f0fdfa]"
          >
            {state === 'done' ? '已记录 ✓' : state === 'loading' ? '保存中…' : '📝 记笔记'}
          </Button>
        )}
      </div>
    </div>
  )
}

import { forwardRef, type KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'

const MAX_LENGTH = 2000

interface Props {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  busy: boolean
  thinking: boolean
  selected: { turnId: string; errorId: string } | null
  onClearSelected: () => void
}

const ChatComposer = forwardRef<HTMLTextAreaElement, Props>(function ChatComposer(
  { value, onChange, onSend, busy, thinking, selected, onClearSelected },
  ref,
) {
  const over = value.length > MAX_LENGTH
  const disabled = busy || over || value.trim().length === 0

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== 'Enter') return
    if (e.shiftKey) return
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    e.preventDefault()
    if (!disabled) onSend()
  }

  function autoResize(el: HTMLTextAreaElement) {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="shrink-0 border-t border-[#dee2e6] bg-white px-4 py-3 md:px-8">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className="h-5 text-xs text-[#868e96]"
          aria-live="polite"
          data-testid="thinking-indicator"
        >
          {thinking ? '思考中…' : ''}
        </div>
        {selected && (
          <div className="mb-2 flex items-center gap-2">
            <span className="rounded-full bg-[#e6fcf5] px-3 py-1 text-xs text-[#0a7053]">
              正在追问 {selected.turnId}:{selected.errorId}
            </span>
            <button
              type="button"
              onClick={onClearSelected}
              aria-label="取消追问目标"
              className="text-xs text-[#868e96] hover:text-[#495057]"
            >
              ×
            </button>
          </div>
        )}
        <div className="flex items-end gap-2">
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => {
              onChange(e.target.value)
              autoResize(e.target)
            }}
            onKeyDown={handleKeyDown}
            placeholder={
              selected
                ? '输入追问，例如：为什么这么改？'
                : '输入英文纠错，或继续追问'
            }
            rows={1}
            className="min-h-11 min-w-0 flex-1 resize-none rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
          />
          <Button
            type="button"
            onClick={onSend}
            disabled={disabled}
            className="h-11 shrink-0 bg-[#0ca678] px-5 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
          >
            {busy ? '分析中…' : selected ? '发送追问' : '发送'}
          </Button>
        </div>
        <div className="mt-1 flex justify-between text-xs text-[#868e96]">
          <span>{selected ? 'Enter 发送追问，Shift+Enter 换行' : 'Enter 发送，Shift+Enter 换行'}</span>
          <span className={over ? 'text-[#fa5252]' : ''}>
            {over ? '请缩短至 2000 字符以内' : `${value.length}/${MAX_LENGTH}`}
          </span>
        </div>
      </div>
    </div>
  )
})

export default ChatComposer

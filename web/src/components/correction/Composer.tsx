import { useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useConversation } from '@/store/conversation-context'

const MAX_LENGTH = 2000

export default function Composer() {
  const { send, pending } = useConversation()
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const submittingRef = useRef(false)

  const over = text.length > MAX_LENGTH
  const disabled = pending || submittingRef.current || text.trim().length === 0 || over

  function autoResize() {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  async function handleSend() {
    const content = text.trim()
    if (!content || disabled || submittingRef.current) return
    submittingRef.current = true
    setText('')
    if (ref.current) ref.current.style.height = 'auto'
    try {
      await send(content)
    } finally {
      submittingRef.current = false
    }
  }

  return (
    <div className="shrink-0 border-t border-[#dee2e6] bg-white px-4 py-3 md:px-8">
      <div className="mx-auto max-w-2xl">
        <textarea
          ref={ref}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            autoResize()
          }}
          placeholder="输入英文，AI 将为你纠错；也可以随时提问"
          rows={1}
          className="w-full resize-none rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
        />
        <div className="mt-1.5 flex items-center justify-between">
          <span className={`text-sm ${over ? 'text-[#fa5252]' : 'text-[#868e96]'}`}>
            {over ? '请将文本缩短至 2000 字符以内再提交' : `${text.length}/${MAX_LENGTH}`}
          </span>
          <Button
            onClick={handleSend}
            disabled={disabled}
            className="h-11 bg-[#0ca678] px-6 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
          >
            {pending ? 'AI 正在分析，请稍候…' : '发送'}
          </Button>
        </div>
      </div>
    </div>
  )
}

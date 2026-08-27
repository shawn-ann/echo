import { useRef, useState, type KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'
import { useConversation } from '@/store/conversation-context'

const MAX_LENGTH = 2000

export default function Composer() {
  const { send, pending } = useConversation()
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const submittingRef = useRef(false)
  const userTypedRef = useRef(false)

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
    const prevText = text
    userTypedRef.current = false
    setText('')
    if (ref.current) ref.current.style.height = 'auto'
    try {
      const ok = await send(content)
      if (!ok && !userTypedRef.current) setText(prevText)
    } finally {
      submittingRef.current = false
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== 'Enter') return
    // Shift+Enter：默认换行，不拦截
    if (e.shiftKey) return
    // IME 合成期（中文输入法选词）回车仅确认候选词，不触发发送
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    e.preventDefault()
    if (!disabled) handleSend()
  }

  return (
    <div className="shrink-0 border-t border-[#dee2e6] bg-white px-4 py-3 md:px-8">
      <div className="mx-auto w-full">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 md:flex-nowrap md:gap-3">
          <textarea
            ref={ref}
            value={text}
            onChange={(e) => {
              userTypedRef.current = true
              setText(e.target.value)
              autoResize()
            }}
            onKeyDown={handleKeyDown}
            placeholder="输入英文，AI 将为你纠错"
            rows={1}
            className="min-w-0 flex-1 resize-none rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
          />
          <Button
            onClick={handleSend}
            disabled={disabled}
            className="h-11 shrink-0 bg-[#0ca678] px-6 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8] md:order-2"
          >
            {pending ? 'AI 正在分析，请稍候…' : '发送'}
          </Button>
          <span
            className={`basis-full text-sm md:order-1 md:basis-auto ${over ? 'text-[#fa5252]' : 'text-[#868e96]'}`}
          >
            {over ? '请将文本缩短至 2000 字符以内再提交' : `${text.length}/${MAX_LENGTH}`}
          </span>
        </div>
      </div>
    </div>
  )
}

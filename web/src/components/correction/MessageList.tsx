import { useEffect, useRef } from 'react'

import CorrectionReportCard from '@/components/correction/CorrectionReportCard'
import LoadingBubble from '@/components/correction/LoadingBubble'
import ReplyBubble from '@/components/correction/ReplyBubble'
import UserBubble from '@/components/correction/UserBubble'
import { useConversation } from '@/store/conversation-context'

export default function MessageList() {
  const { messages, pending, error } = useConversation()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, pending])

  if (messages.length === 0 && !pending) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="text-center text-[#868e96]">
          输入英文，AI 将为你纠错；也可以随时提问
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-2xl flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
      {messages.map((m) =>
        m.role === 'user' ? (
          <UserBubble key={m.id} content={m.content ?? ''} />
        ) : m.type === 'report' && m.report ? (
          <CorrectionReportCard key={m.id} report={m.report} />
        ) : (
          <ReplyBubble key={m.id} content={m.content ?? ''} />
        ),
      )}
      {pending && <LoadingBubble />}
      {error && (
        <p className="text-center text-sm text-[#fa5252]">
          {error}
        </p>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'

import CorrectionReportCard from '@/components/correction/CorrectionReportCard'
import LoadingBubble from '@/components/correction/LoadingBubble'
import UserBubble from '@/components/correction/UserBubble'
import { useConversation } from '@/store/conversation-context'

export default function MessageList() {
  const { messages, pending, pendingStartedAt, error, sessionExpired, retry, relogin } =
    useConversation()
  const [now, setNow] = useState(() => Date.now())
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, pending])

  useEffect(() => {
    if (!pending) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 200)
    return () => window.clearInterval(timer)
  }, [pending])

  const failedTemp = messages.filter((m) => m.id.startsWith('tmp-')).at(-1)

  if (messages.length === 0 && !pending) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[#f8f9fa] p-6">
        <p className="text-center text-[#868e96]">
          输入英文，AI 将为你纠错
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#f8f9fa]">
      <div className="mx-auto w-full min-w-0 space-y-4 p-4 md:p-6">
        {messages.map((m) =>
          m.role === 'user' ? (
            <UserBubble key={m.id} content={m.content ?? ''} />
          ) : m.report ? (
            <CorrectionReportCard
              key={m.id}
              report={m.report}
              durationMs={m.durationMs}
            />
          ) : null,
        )}
        {pending && <LoadingBubble startedAt={pendingStartedAt} now={now} />}
        {sessionExpired && (
          <div className="text-center text-sm text-[#fa5252]">
            <p>会话已过期，请重新登录</p>
            <button
              type="button"
              onClick={relogin}
              className="mt-2 rounded-md border border-[#ced4da] bg-white px-3 py-1 text-[#343a40] hover:bg-[#f1f3f5]"
            >
              重新登录
            </button>
          </div>
        )}
        {error && !sessionExpired && (
          <div className="text-center text-sm text-[#fa5252]">
            <p>{error}</p>
            {failedTemp && (
              <button
                type="button"
                onClick={() => retry(failedTemp.id, failedTemp.content ?? '')}
                className="mt-2 rounded-md border border-[#ced4da] bg-white px-3 py-1 text-[#343a40] hover:bg-[#f1f3f5]"
              >
                重试
              </button>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

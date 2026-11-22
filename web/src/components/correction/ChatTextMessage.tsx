import type { TextChatItem } from '@/types/chat'

export default function ChatTextMessage({ message }: { message: TextChatItem }) {
  if (message.status === 'error') return null

  return (
    <div className="flex justify-start">
      <div
        data-testid="stream-explanation"
        className="max-w-[92%] rounded-xl border border-[#dee2e6] bg-white p-3 text-[#212529]"
      >
        {message.status === 'streaming' && !message.text ? (
          <p className="text-sm text-[#868e96]">正在解释…</p>
        ) : (
          <>
            <p className="mb-1 text-sm font-semibold text-[#343a40]">解释</p>
            <p className="whitespace-pre-wrap text-sm">{message.text}</p>
          </>
        )}
        {message.error && (
          <p className="mt-2 text-sm text-[#c92a2a]">{message.error}</p>
        )}
      </div>
    </div>
  )
}

import ErrorCard from '@/components/correction/ErrorCard'
import StreamRewriteCard from '@/components/correction/StreamRewriteCard'
import type { CorrectionChatItem } from '@/types/chat'

interface Props {
  message: CorrectionChatItem
  onAsk: (errorId: string) => void
}

function RewriteSkeleton({ title, testId }: { title: string; testId: string }) {
  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-[#dee2e6] bg-white p-3"
    >
      <p className="text-sm font-semibold text-[#868e96]">{title}</p>
      <div className="mt-3 space-y-2">
        <div className="h-3 w-4/5 animate-pulse rounded bg-[#e9ecef]" />
        <div className="h-3 w-3/5 animate-pulse rounded bg-[#e9ecef]" />
      </div>
    </div>
  )
}

export default function ChatCorrectionMessage({ message, onAsk }: Props) {
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[92%] rounded-xl border border-[#dee2e6] bg-white p-3">
        <div data-testid="stream-errors" className="rounded-lg border border-[#dee2e6] p-3">
          <p className="mb-2 text-sm font-semibold text-[#343a40]">错误分析</p>
          {message.errors.length > 0 ? (
            <div className="space-y-2">
              {message.errors.map((error) => (
                <ErrorCard
                  key={error.error_id}
                  error={error}
                  onAsk={() => onAsk(error.error_id)}
                />
              ))}
            </div>
          ) : !message.errorsLoaded ? (
            <p className="text-sm text-[#868e96]">思考中…</p>
          ) : (
            <p className="text-sm text-[#0a7053]">未检测到语法错误</p>
          )}
        </div>

        <div className="mt-2">
          {message.minimal ? (
            <StreamRewriteCard
              title="最小修正"
              text={message.minimal.text}
              note={message.minimal.note}
              testId="stream-minimal"
            />
          ) : message.status === 'streaming' ? (
            <RewriteSkeleton title="最小修正" testId="stream-minimal-loading" />
          ) : null}
        </div>

        <div className="mt-2">
          {message.fluency ? (
            <StreamRewriteCard
              title="地道表达"
              text={message.fluency.text}
              note={message.fluency.note}
              testId="stream-fluency"
            />
          ) : message.status === 'streaming' ? (
            <RewriteSkeleton title="地道表达" testId="stream-fluency-loading" />
          ) : null}
        </div>

        {message.degraded.length > 0 && (
          <div className="mt-2 rounded-lg border border-[#ffd43b] bg-[#fff9db] p-3 text-sm text-[#8a6d00]">
            {message.degraded.map((item) => (
              <p key={item}>部分改写生成失败：{item}</p>
            ))}
          </div>
        )}

        {message.error && (
          <div className="mt-2 rounded-lg border border-[#ffc9c9] bg-[#fff5f5] p-3 text-sm text-[#c92a2a]">
            {message.error}
          </div>
        )}
      </div>
    </div>
  )
}

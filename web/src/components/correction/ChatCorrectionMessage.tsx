import ErrorCard from '@/components/correction/ErrorCard'
import RewriteBox from '@/components/correction/RewriteBox'
import type { CorrectionChatItem } from '@/types/chat'

interface Props {
  message: CorrectionChatItem
  onAsk: (errorId: string) => void
}

const NO_ERROR_MESSAGE = '🎉 这段英文写得不错，没有发现语法错误。'
const MINIMAL_EMPTY_MESSAGE = '原文已无需修改。'
const FLUENCY_EMPTY_MESSAGE = '暂无可优化空间，这版表达已足够自然。'

function sameText(a: string, b: string) {
  return a.trim() === b.trim()
}

export default function ChatCorrectionMessage({ message, onAsk }: Props) {
  const streaming = message.status === 'streaming'
  const sourceText = message.sourceText
  const minimalText = message.minimal?.text ?? sourceText
  const minimalEmpty = !!message.minimal && sameText(message.minimal.text, sourceText)
  const fluencyEmpty = !!message.fluency && sameText(message.fluency.text, minimalText)

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
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
            <p className="text-sm text-[#0a7053]">{NO_ERROR_MESSAGE}</p>
          )}
        </div>

        <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
          <p className="mb-2 text-sm font-semibold text-[#343a40]">改写</p>
          <div className="space-y-2">
            {message.minimal ? (
              <RewriteBox
                label="最小修正"
                icon="✏️"
                accent="text-[#2b8a3e]"
                text={message.minimal.text}
                note={message.minimal.note}
                emptyMessage={minimalEmpty ? MINIMAL_EMPTY_MESSAGE : undefined}
                testId="stream-minimal"
              />
            ) : streaming ? (
              <RewriteBox
                label="最小修正"
                icon="✏️"
                accent="text-[#2b8a3e]"
                loading
                testId="stream-minimal"
              />
            ) : null}

            {message.fluency ? (
              <RewriteBox
                label="地道表达"
                icon="✨"
                accent="text-[#7048e8]"
                text={message.fluency.text}
                note={message.fluency.note}
                emptyMessage={fluencyEmpty ? FLUENCY_EMPTY_MESSAGE : undefined}
                testId="stream-fluency"
              />
            ) : streaming ? (
              <RewriteBox
                label="地道表达"
                icon="✨"
                accent="text-[#7048e8]"
                loading
                testId="stream-fluency"
              />
            ) : null}
          </div>
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

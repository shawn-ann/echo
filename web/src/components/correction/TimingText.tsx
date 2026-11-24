import { formatSeconds } from '@/lib/time'

interface Props {
  startedAt?: number
  thinkingMs?: number | null
  doneMs?: number | null
  now?: number
  testId?: string
}

export default function TimingText({ startedAt, thinkingMs, doneMs, now, testId }: Props) {
  const elapsed =
    doneMs ?? (startedAt != null && now != null ? now - startedAt : null)
  if (elapsed == null) return null

  let text: string
  if (doneMs != null) {
    text =
      thinkingMs != null
        ? `思考 ${formatSeconds(thinkingMs)} · 总耗时 ${formatSeconds(doneMs)}`
        : `总耗时 ${formatSeconds(doneMs)}`
  } else {
    text =
      thinkingMs != null
        ? `思考 ${formatSeconds(thinkingMs)} · 已用时 ${formatSeconds(elapsed)}`
        : `已用时 ${formatSeconds(elapsed)}`
  }

  return (
    <span
      data-testid={testId}
      className="text-xs text-[#868e96]"
      aria-live="polite"
    >
      {text}
    </span>
  )
}

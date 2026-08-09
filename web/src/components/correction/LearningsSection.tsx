import type { Learning } from '@/api/messages'

function WrongRightRow({ wrong, right }: { wrong: string; right: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="rounded bg-[#fff5f5] px-2 py-0.5 text-xs text-[#c92a2a]">
        {wrong} ❌
      </span>
      <span className="text-[#adb5bd]">→</span>
      <span className="rounded bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#2b8a3e]">
        {right} ✅
      </span>
    </div>
  )
}

export default function LearningsSection({ learnings }: { learnings: Learning[] }) {
  if (learnings.length === 0) return null
  return (
    <div className="rounded-lg bg-[#f8f9fa] p-3">
      <p className="mb-2 text-sm font-semibold text-[#0a7053]">📚 学到的规则</p>
      <div className="space-y-2">
        {learnings.map((l, i) => (
          <div key={`${i}-${l.title}`} className="rounded-lg border border-[#dee2e6] bg-white p-3">
            <p className="text-sm font-semibold text-[#343a40]">{l.title}</p>
            <p className="mt-0.5 text-xs text-[#495057]">{l.rule}</p>
            {l.instances.length > 0 && (
              <div className="mt-2 flex flex-col gap-1.5">
                {l.instances.map((inst, j) => (
                  <WrongRightRow key={j} wrong={inst.wrong} right={inst.right} />
                ))}
              </div>
            )}
            {l.examples.length > 0 && (
              <div className="mt-2 flex flex-col gap-1.5 border-t border-dashed border-[#dee2e6] pt-2">
                {l.examples.map((ex, j) => (
                  <span
                    key={j}
                    className="rounded border border-[#ffd8a8] bg-[#fff9f0] px-2 py-0.5 text-xs text-[#e8590c]"
                  >
                    例句：{ex.wrong} ❌ → {ex.right} ✅
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

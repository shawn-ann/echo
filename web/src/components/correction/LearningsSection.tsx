import type { Learning } from '@/api/messages'

function ExampleRow({ example }: { example: string }) {
  const [wrong, right] = example.split('→').map((s) => s.trim())
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rounded bg-[#fff5f5] px-2 py-0.5 text-xs text-[#c92a2a]">
        {wrong ?? example} ❌
      </span>
      <span className="text-[#adb5bd]">→</span>
      <span className="rounded bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#2b8a3e]">
        {right ?? ''} ✅
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
          <div key={`${i}-${l.rule}`} className="rounded-lg border border-[#dee2e6] bg-white p-3">
            <p className="text-xs text-[#495057]">{l.rule}</p>
            {l.example && (
              <div className="mt-2">
                <ExampleRow example={l.example} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

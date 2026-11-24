import type { CorrectionReport } from '@/api/messages'
import ErrorCard from '@/components/correction/ErrorCard'
import RewriteSection from '@/components/correction/RewriteSection'
import TimingText from '@/components/correction/TimingText'

interface Props {
  report: CorrectionReport
  durationMs?: number
}

export default function CorrectionReportCard({ report, durationMs }: Props) {
  if (!report.has_errors) {
    const rewrite = report.rewrite
    const showNatural = !!rewrite && rewrite.natural.text.trim() !== ''

    return (
      <div className="flex justify-start">
        <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
          <div className="mb-1 flex justify-end">
            <TimingText doneMs={durationMs} testId="correction-timing" />
          </div>
          <div className="rounded-xl bg-[#e6fcf5] px-4 py-2.5 text-[#0a7053]">
            🎉 这段英文写得不错，没有发现语法错误。
          </div>
          {showNatural && (
            <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
              <p className="mb-2 text-sm font-semibold text-[#343a40]">也可以这样写</p>
              <RewriteSection rewrite={rewrite!} show="natural-only" />
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
        <div className="mb-1 flex justify-end">
          <TimingText doneMs={durationMs} testId="correction-timing" />
        </div>
        <div className="rounded-lg border border-[#dee2e6] p-3">
          <p className="mb-2 text-sm font-semibold text-[#343a40]">错误分析</p>
          <div className="space-y-2">
            {report.errors.map((e, i) => (
              <ErrorCard key={`${i}-${e.fragment}`} error={e} />
            ))}
          </div>
        </div>
        {report.rewrite && (
          <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
            <p className="mb-2 text-sm font-semibold text-[#343a40]">改写</p>
            <RewriteSection rewrite={report.rewrite} />
          </div>
        )}
      </div>
    </div>
  )
}

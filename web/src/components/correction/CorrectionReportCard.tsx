import type { CorrectionReport } from '@/api/messages'
import ErrorCard from '@/components/correction/ErrorCard'
import RewriteSection from '@/components/correction/RewriteSection'

export default function CorrectionReportCard({ report }: { report: CorrectionReport }) {
  if (!report.has_errors) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-xl bg-[#e6fcf5] px-4 py-2.5 text-[#0a7053] md:max-w-[70%]">
          🎉 这段英文写得不错，没有发现语法或不地道的表达！
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3 md:max-w-[75%]">
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

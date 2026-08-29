import { useState } from 'react'

import { useConversation } from '@/store/conversation-context'
import type { CorrectionReport, ErrorBlock, Message } from '@/api/messages'
import ErrorCard from '@/components/correction/ErrorCard'
import LearningsSection from '@/components/correction/LearningsSection'
import RewriteSection from '@/components/correction/RewriteSection'
import { Button } from '@/components/ui/button'

type SaveState = 'idle' | 'loading' | 'done'

interface Props {
  report: CorrectionReport
  message: Message
  sourceText: string
}

export default function CorrectionReportCard({ report, message, sourceText }: Props) {
  const { saveNote } = useConversation()
  const [batchState, setBatchState] = useState<SaveState>('idle')
  const [errorStates, setErrorStates] = useState<Record<number, SaveState>>({})
  const [toast, setToast] = useState<string | null>(null)

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }

  async function handleSaveOne(index: number, error: ErrorBlock) {
    setErrorStates((prev) => ({ ...prev, [index]: 'loading' }))
    const result = await saveNote(message.id, sourceText, [error])
    if (result.success && result.ruleTitles) {
      setErrorStates((prev) => ({ ...prev, [index]: 'done' }))
      showToast(`已记入「${result.ruleTitles[0]}」`)
    } else {
      setErrorStates((prev) => ({ ...prev, [index]: 'idle' }))
      showToast(result.error ?? '保存失败，请重试')
    }
  }

  async function handleSaveAll() {
    if (batchState !== 'idle') return
    setBatchState('loading')
    const result = await saveNote(message.id, sourceText, report.errors)
    if (result.success) {
      setBatchState('done')
      showToast(`已记入 ${result.ruleTitles?.length ?? 0} 条规则笔记`)
    } else {
      setBatchState('idle')
      showToast(result.error ?? '保存失败，请重试')
    }
  }

  if (!report.has_errors) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-xl bg-[#e6fcf5] px-4 py-2.5 text-[#0a7053] md:max-w-[90%]">
          🎉 这段英文写得不错，没有发现语法或不地道的表达！
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
        <div className="rounded-lg border border-[#dee2e6] p-3">
          <p className="mb-2 text-sm font-semibold text-[#343a40]">错误分析</p>
          <div className="space-y-2">
            {report.errors.map((e, i) => (
              <ErrorCard
                key={`${i}-${e.fragment}`}
                error={e}
                state={errorStates[i] ?? 'idle'}
                onSave={() => handleSaveOne(i, e)}
              />
            ))}
          </div>
        </div>
        {report.rewrite && (
          <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
            <p className="mb-2 text-sm font-semibold text-[#343a40]">改写</p>
            <RewriteSection rewrite={report.rewrite} />
          </div>
        )}
        <div className="mt-2">
          <LearningsSection learnings={report.learnings ?? []} />
        </div>
        <div className="mt-2 flex justify-end">
          <Button
            variant="outline"
            size="sm"
            disabled={batchState !== 'idle'}
            onClick={handleSaveAll}
            className="border-[#0ca678] text-[#0ca678] hover:bg-[#f0fdfa]"
          >
            {batchState === 'done' ? '已记录 ✓' : batchState === 'loading' ? '保存中…' : '📝 全部记笔记'}
          </Button>
        </div>
        {toast && (
          <div className="mt-2 rounded-lg bg-[#f1f3f5] px-3 py-1.5 text-sm text-[#495057]">
            {toast}
          </div>
        )}
      </div>
    </div>
  )
}

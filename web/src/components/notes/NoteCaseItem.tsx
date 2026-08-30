import { useState } from 'react'

import type { NoteCaseItem } from '@/api/notes'
import { Button } from '@/components/ui/button'

interface Props {
  caseItem: NoteCaseItem
  noteId: string
  onDeleted: (caseId: string) => Promise<boolean>
}

export default function NoteCaseItem({ caseItem, onDeleted }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    setDeleting(true)
    const ok = await onDeleted(caseItem.id)
    if (!ok) {
      setDeleting(false)
      setConfirming(false)
    }
  }

  return (
    <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-[#fff5f5] px-2 py-0.5 text-xs text-[#c92a2a]">
          {caseItem.fragment} ❌
        </span>
        <span className="text-[#adb5bd]">→</span>
        <span className="rounded bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#2b8a3e]">
          {caseItem.correction} ✅
        </span>
      </div>
      <p className="mt-1.5 text-xs text-[#868e96]">原文：{caseItem.source_text}</p>
      <div className="mt-2 flex justify-end">
        {confirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#868e96]">确认删除？</span>
            <Button variant="destructive" size="xs" disabled={deleting} onClick={handleDelete}>
              {deleting ? '删除中…' : '确认'}
            </Button>
            <Button variant="ghost" size="xs" onClick={() => setConfirming(false)}>
              取消
            </Button>
          </div>
        ) : (
          <Button variant="ghost" size="xs" onClick={() => setConfirming(true)} className="text-[#868e96]">
            ×
          </Button>
        )}
      </div>
    </div>
  )
}

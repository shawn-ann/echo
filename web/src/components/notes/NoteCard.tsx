import { useState } from 'react'

import { deleteNote, deleteNoteCase, fetchNoteDetail } from '@/api/notes'
import type { NoteListItem, NoteDetailResponse } from '@/api/notes'
import { Button } from '@/components/ui/button'
import NoteCaseItem from '@/components/notes/NoteCaseItem'

interface Props {
  note: NoteListItem
  onNoteDeleted: (noteId: string) => void
}

export default function NoteCard({ note, onNoteDeleted }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState<NoteDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [caseCount, setCaseCount] = useState(note.case_count)

  async function toggleExpand() {
    if (!expanded && !detail) {
      setLoading(true)
      try {
        const d = await fetchNoteDetail(note.id)
        setDetail(d)
      } catch {
        // 静默
      } finally {
        setLoading(false)
      }
    }
    setExpanded(!expanded)
  }

  async function handleCaseDeleted(caseId: string): Promise<boolean> {
    try {
      await deleteNoteCase(note.id, caseId)
      if (detail) {
        const newCases = detail.cases.filter((c) => c.id !== caseId)
        if (newCases.length === 0) {
          onNoteDeleted(note.id)
        } else {
          setDetail({ ...detail, cases: newCases })
          setCaseCount((prev) => prev - 1)
        }
      }
      return true
    } catch {
      return false
    }
  }

  async function handleDeleteNote() {
    try {
      await deleteNote(note.id)
      onNoteDeleted(note.id)
    } catch {
      // 静默
    }
  }

  return (
    <div className="rounded-xl border border-[#dee2e6] bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <button type="button" onClick={toggleExpand} className="flex-1 text-left">
          <p className="text-sm font-semibold text-[#343a40]">{note.rule_title}</p>
          <p className="mt-0.5 line-clamp-1 text-xs text-[#868e96]">{note.knowledge_point}</p>
          <p className="mt-1 text-xs text-[#adb5bd]">
            {caseCount} 个案例 · 最近更新 {new Date(note.updated_at).toLocaleDateString()}
          </p>
        </button>
        <span className="text-[#adb5bd]">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2">
          {loading ? (
            <p className="text-sm text-[#868e96]">加载中…</p>
          ) : detail ? (
            <>
              <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                <p className="mb-1 text-sm font-semibold text-[#343a40]">📌 核心知识点</p>
                <p className="text-sm text-[#495057]">{detail.knowledge_point}</p>
              </div>

              <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                <p className="mb-1 text-sm font-semibold text-[#343a40]">⚠️ 个人易错警示</p>
                <p className="text-sm text-[#495057]">{detail.warning}</p>
              </div>

              {detail.alternatives.length > 0 && (
                <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                  <p className="mb-2 text-sm font-semibold text-[#343a40]">💼 职场同义备选</p>
                  <div className="space-y-1.5">
                    {detail.alternatives.map((alt, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-[#0ca678]">•</span>
                        <span className="text-[#212529]">{alt}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                <p className="mb-1 text-sm font-semibold text-[#343a40]">❓ 费曼自测</p>
                <p className="text-sm text-[#495057]">{detail.feynman_question}</p>
              </div>

              {detail.cases.length > 0 && (
                <p className="pt-1 text-sm font-semibold text-[#343a40]">📝 我的错误</p>
              )}
              {detail.cases.map((c) => (
                <NoteCaseItem key={c.id} caseItem={c} onDeleted={handleCaseDeleted} />
              ))}
              <div className="flex justify-end pt-2">
                {confirmDelete ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#868e96]">确认删除该笔记？</span>
                    <Button variant="destructive" size="xs" onClick={handleDeleteNote}>
                      确认
                    </Button>
                    <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(false)}>
                      取消
                    </Button>
                  </div>
                ) : (
                  <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(true)} className="text-[#fa5252]">
                    删除该笔记
                  </Button>
                )}
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}

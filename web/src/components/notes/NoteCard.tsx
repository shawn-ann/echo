import { useState } from 'react'

import { deleteNote, deleteNoteCase, fetchNoteDetail, updateNote } from '@/api/notes'
import type { NoteListItem, NoteDetailResponse } from '@/api/notes'
import { Button } from '@/components/ui/button'
import NoteCaseItem from '@/components/notes/NoteCaseItem'

interface Props {
  note: NoteListItem
  onNoteDeleted: (noteId: string) => void
  onNoteUpdated: (updated: NoteDetailResponse) => void
}

export default function NoteCard({ note, onNoteDeleted, onNoteUpdated }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState<NoteDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [caseCount, setCaseCount] = useState(note.case_count)

  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editKnowledgePoint, setEditKnowledgePoint] = useState('')
  const [editAlternatives, setEditAlternatives] = useState<string[]>([])
  const [editFeynman, setEditFeynman] = useState('')
  const [editingErrors, setEditingErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

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

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }

  function handleEditStart() {
    if (!detail) return
    setEditTitle(detail.rule_title)
    setEditKnowledgePoint(detail.knowledge_point)
    setEditAlternatives([...detail.alternatives])
    setEditFeynman(detail.feynman_question)
    setEditingErrors([])
    setEditing(true)
  }

  function handleEditCancel() {
    setEditing(false)
    setEditingErrors([])
  }

  function validateEdit(): string[] {
    const errors: string[] = []
    if (!editTitle.trim()) errors.push('规则标题不能为空')
    if (!editKnowledgePoint.trim()) errors.push('核心知识点不能为空')
    if (!editFeynman.trim()) errors.push('费曼自测不能为空')
    return errors
  }

  async function handleSave() {
    const errors = validateEdit()
    if (errors.length > 0) {
      setEditingErrors(errors)
      return
    }
    setSaving(true)
    try {
      const updated = await updateNote(note.id, {
        rule_title: editTitle.trim(),
        knowledge_point: editKnowledgePoint.trim(),
        alternatives: editAlternatives.filter((a) => a.trim() !== ''),
        feynman_question: editFeynman.trim(),
      })
      setDetail(updated)
      onNoteUpdated(updated)
      setEditing(false)
      setEditingErrors([])
      showToast('✓ 笔记已保存')
    } catch {
      showToast('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  function handleAltChange(i: number, value: string) {
    setEditAlternatives((prev) => prev.map((a, idx) => (idx === i ? value : a)))
  }

  function handleAltRemove(i: number) {
    setEditAlternatives((prev) => prev.filter((_, idx) => idx !== i))
  }

  function handleAltAdd() {
    setEditAlternatives((prev) => [...prev, ''])
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
            editing ? (
              <div className="space-y-2 rounded-xl border border-[#0ca678] bg-white p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-[#343a40]">✏️ 编辑笔记</p>
                  <span className="rounded-full bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#0ca678]">编辑中</span>
                </div>
                <div>
                  <p className="mb-1 text-sm font-semibold text-[#343a40]">🏷 规则标题</p>
                  <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="w-full rounded-lg border border-[#ced4da] px-3 py-2 text-sm focus:border-[#0ca678] focus:outline-none" />
                </div>
                <div>
                  <p className="mb-1 text-sm font-semibold text-[#343a40]">📌 核心知识点</p>
                  <textarea value={editKnowledgePoint} onChange={(e) => setEditKnowledgePoint(e.target.value)} className="w-full rounded-lg border border-[#ced4da] px-3 py-2 text-sm focus:border-[#0ca678] focus:outline-none" />
                </div>
                <div>
                  <p className="mb-1 text-sm font-semibold text-[#343a40]">💼 同义备选</p>
                  <div className="space-y-1.5">
                    {editAlternatives.map((alt, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <input value={alt} onChange={(e) => handleAltChange(i, e.target.value)} className="flex-1 rounded-lg border border-[#ced4da] px-3 py-1.5 text-sm focus:border-[#0ca678] focus:outline-none" />
                        <button type="button" onClick={() => handleAltRemove(i)} className="shrink-0 text-[#fa5252]">✕</button>
                      </div>
                    ))}
                  </div>
                  <button type="button" onClick={handleAltAdd} className="mt-1 rounded border border-dashed border-[#0ca678] px-2 py-0.5 text-xs text-[#0ca678]">＋ 添加一条</button>
                </div>
                <div>
                  <p className="mb-1 text-sm font-semibold text-[#343a40]">❓ 费曼自测</p>
                  <textarea value={editFeynman} onChange={(e) => setEditFeynman(e.target.value)} className="w-full rounded-lg border border-[#ced4da] px-3 py-2 text-sm focus:border-[#0ca678] focus:outline-none" />
                </div>
                {editingErrors.length > 0 && (
                  <div className="rounded-lg border border-[#fa5252] bg-[#fff5f5] px-3 py-2 text-xs text-[#c92a2a]">
                    {editingErrors.map((err) => <p key={err}>{err}</p>)}
                  </div>
                )}
                <div className="flex items-center justify-between pt-1">
                  <p className="text-xs text-[#868e96]">修改仅作用于这条规则，不会改动纠错记录</p>
                  <div className="flex gap-2">
                    <button type="button" onClick={handleEditCancel} className="rounded px-3 py-1 text-xs text-[#495057]">取消</button>
                    <button type="button" disabled={saving} onClick={handleSave} className="rounded bg-[#0ca678] px-4 py-1 text-xs text-white disabled:opacity-50">
                      {saving ? '保存中…' : '保存'}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                  <p className="mb-1 text-sm font-semibold text-[#343a40]">📌 核心知识点</p>
                  <p className="text-sm text-[#495057]">{detail.knowledge_point}</p>
                </div>

                {detail.alternatives.length > 0 && (
                  <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                    <p className="mb-2 text-sm font-semibold text-[#343a40]">💼 同义备选</p>
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
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="xs" onClick={handleEditStart} className="text-[#0ca678]">
                        ✏️ 编辑此笔记
                      </Button>
                      <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(true)} className="text-[#fa5252]">
                        删除该笔记
                      </Button>
                    </div>
                  )}
                </div>
              </>
            )
          ) : null}
        </div>
      )}

      {toast && (
        <div className="fixed right-4 top-4 z-50 rounded-lg bg-[#0ca678] px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}

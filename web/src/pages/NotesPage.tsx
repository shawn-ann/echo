import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchNotes } from '@/api/notes'
import type { NoteListItem } from '@/api/notes'
import { Button } from '@/components/ui/button'
import NoteCard from '@/components/notes/NoteCard'

export default function NotesPage() {
  const [notes, setNotes] = useState<NoteListItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchNotes()
      setNotes(data)
    } catch {
      // 静默
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function handleNoteDeleted(noteId: string) {
    setNotes((prev) => prev.filter((n) => n.id !== noteId))
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[#868e96]">
        加载中…
      </div>
    )
  }

  if (notes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-[#868e96]">
        <p>还没有笔记</p>
        <Button
          variant="outline"
          onClick={() => navigate('/correction')}
          className="border-[#0ca678] text-[#0ca678] hover:bg-[#f0fdfa]"
        >
          去纠错页记下你的第一条规则
        </Button>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="mx-auto max-w-2xl space-y-3">
        <h1 className="text-lg font-semibold text-[#343a40]">我的笔记</h1>
        {notes.map((note) => (
          <NoteCard key={note.id} note={note} onNoteDeleted={handleNoteDeleted} />
        ))}
      </div>
    </div>
  )
}

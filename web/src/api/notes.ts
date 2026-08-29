import { http } from './client'
import type { ErrorBlock } from './messages'

export interface SavedNoteItem {
  note_id: string
  rule_title: string
  is_new: boolean
  case_id: string
}

export interface SaveNoteResponse {
  saved_notes: SavedNoteItem[]
}

export interface NoteListItem {
  id: string
  rule_title: string
  description: string
  case_count: number
  updated_at: string
}

export interface NoteListResponse {
  notes: NoteListItem[]
}

export interface NoteCaseItem {
  id: string
  example: string
  source_text: string
  created_at: string
}

export interface NoteDetailResponse {
  id: string
  rule_title: string
  description: string
  cases: NoteCaseItem[]
}

export async function saveNote(
  messageId: string,
  sourceText: string,
  errors: ErrorBlock[],
): Promise<SaveNoteResponse> {
  return http.post<SaveNoteResponse>('/notes/save', {
    message_id: messageId,
    source_text: sourceText,
    errors,
  })
}

export async function fetchNotes(): Promise<NoteListItem[]> {
  const data = await http.get<NoteListResponse>('/notes')
  return data.notes
}

export async function fetchNoteDetail(noteId: string): Promise<NoteDetailResponse> {
  return http.get<NoteDetailResponse>(`/notes/${noteId}`)
}

export async function deleteNote(noteId: string): Promise<void> {
  await http.delete<void>(`/notes/${noteId}`)
}

export async function deleteNoteCase(
  noteId: string,
  caseId: string,
): Promise<void> {
  await http.delete<void>(`/notes/${noteId}/cases/${caseId}`)
}

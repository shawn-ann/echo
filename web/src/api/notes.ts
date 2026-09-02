import { http } from './client'

export interface NoteListItem {
  id: string
  rule_title: string
  knowledge_point: string
  case_count: number
  updated_at: string
}

export interface NoteListResponse {
  notes: NoteListItem[]
}

export interface NoteCaseItem {
  id: string
  original_sentence: string
  polished_sentence: string
  change_details: string
  error_root: string
  created_at: string
}

export interface NoteDetailResponse {
  id: string
  rule_title: string
  knowledge_point: string
  alternatives: string[]
  feynman_question: string
  cases: NoteCaseItem[]
}

export interface UpdateNoteRequest {
  rule_title: string
  knowledge_point: string
  alternatives: string[]
  feynman_question: string
}

export async function updateNote(
  noteId: string,
  payload: UpdateNoteRequest,
): Promise<NoteDetailResponse> {
  return http.put<NoteDetailResponse>(`/notes/${noteId}`, payload)
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

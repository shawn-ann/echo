import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.correction import ErrorBlock


class SaveNoteRequest(BaseModel):
    message_id: uuid.UUID
    source_text: str = Field(min_length=1, max_length=2000)
    errors: list[ErrorBlock] = Field(min_length=1)


class NoteRuleResult(BaseModel):
    rule_title: str
    description: str
    example: str


class NoteLLMResponse(BaseModel):
    results: list[NoteRuleResult]


class SavedNoteItem(BaseModel):
    note_id: uuid.UUID
    rule_title: str
    is_new: bool
    case_id: uuid.UUID


class SaveNoteResponse(BaseModel):
    saved_notes: list[SavedNoteItem]


class NoteListItem(BaseModel):
    id: uuid.UUID
    rule_title: str
    description: str
    case_count: int
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteListItem]


class NoteCaseItem(BaseModel):
    id: uuid.UUID
    example: str
    source_text: str
    created_at: datetime


class NoteDetailResponse(BaseModel):
    id: uuid.UUID
    rule_title: str
    description: str
    cases: list[NoteCaseItem]

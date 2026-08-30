import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.correction import ErrorBlock


class SaveNoteRequest(BaseModel):
    message_id: uuid.UUID
    source_text: str = Field(min_length=1, max_length=2000)
    errors: list[ErrorBlock] = Field(min_length=1)


class NoteExample(BaseModel):
    text: str
    note: str


class NoteRuleResult(BaseModel):
    rule_title: str
    description: str
    examples: list[NoteExample] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


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


class NoteSaveAccepted(BaseModel):
    accepted: bool


class NoteListResponse(BaseModel):
    notes: list[NoteListItem]


class NoteCaseItem(BaseModel):
    id: uuid.UUID
    fragment: str
    correction: str
    source_text: str
    created_at: datetime


class NoteDetailResponse(BaseModel):
    id: uuid.UUID
    rule_title: str
    description: str
    examples: list[NoteExample]
    cases: list[NoteCaseItem]

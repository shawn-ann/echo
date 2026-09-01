import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteRuleCase(BaseModel):
    """LLM 输出的单个规则下的案例（change_details 由 LLM 生成）"""
    change_details: str


class NoteRuleResult(BaseModel):
    """LLM 输出的单个规则（8 字段中的规则级字段 + 案例）"""
    rule_title: str
    knowledge_point: str
    warning: str
    alternatives: list[str] = Field(default_factory=list)
    feynman_question: str
    error_root: str
    cases: list[NoteRuleCase] = Field(default_factory=list)


class NoteLLMResponse(BaseModel):
    results: list[NoteRuleResult]


class NoteListItem(BaseModel):
    id: uuid.UUID
    rule_title: str
    knowledge_point: str
    case_count: int
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteListItem]


class NoteCaseItem(BaseModel):
    id: uuid.UUID
    original_sentence: str
    polished_sentence: str
    change_details: str
    error_root: str
    created_at: datetime


class NoteDetailResponse(BaseModel):
    id: uuid.UUID
    rule_title: str
    knowledge_point: str
    warning: str
    alternatives: list[str]
    feynman_question: str
    cases: list[NoteCaseItem]

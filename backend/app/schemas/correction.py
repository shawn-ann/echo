import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ErrorBlock(BaseModel):
    error_type: str
    fragment: str
    explanation: str
    correction: str


class RewriteOption(BaseModel):
    text: str
    note: str


class RewriteSection(BaseModel):
    minimal: RewriteOption
    natural: RewriteOption


class Learning(BaseModel):
    rule: str
    example: str


class CorrectionBody(BaseModel):
    """LLM 单轮纠错输出（无 intent/reply）。"""

    has_errors: bool
    errors: list[ErrorBlock] = Field(default_factory=list)
    rewrite: RewriteSection | None = None
    learnings: list[Learning] = Field(default_factory=list)


class SubmitRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    type: str
    content: str | None
    report: dict | None = None
    created_at: datetime


class SubmitResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


class HistoryResponse(BaseModel):
    messages: list[MessageOut]

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    grammar = "grammar"
    collocation = "collocation"
    chinglish = "chinglish"
    style = "style"


class ErrorBlock(BaseModel):
    category: ErrorCategory
    fragment: str
    explanation: str
    correction: str


class RewriteOption(BaseModel):
    text: str
    explanation: str


class RewriteSection(BaseModel):
    minimal: RewriteOption
    natural: RewriteOption


class WrongRightPair(BaseModel):
    wrong: str
    right: str


class Learning(BaseModel):
    title: str
    rule: str
    instances: list[WrongRightPair] = Field(default_factory=list)
    examples: list[WrongRightPair] = Field(default_factory=list)


class CorrectionBody(BaseModel):
    has_errors: bool
    errors: list[ErrorBlock] = Field(default_factory=list)
    rewrite: RewriteSection | None = None
    learnings: list[Learning] = Field(default_factory=list)


class LLMResponse(BaseModel):
    intent: Literal["correction", "follow_up"]
    correction: CorrectionBody | None = None
    reply: str | None = None


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

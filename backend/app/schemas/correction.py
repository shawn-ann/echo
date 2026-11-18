import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class ErrorBlock(BaseModel):
    category: str
    fragment: str
    explanation: str
    correction: str


class RewriteOption(BaseModel):
    text: str
    note: str


class RewriteSection(BaseModel):
    minimal: RewriteOption
    natural: RewriteOption


class CorrectionBody(BaseModel):
    """LLM 单轮纠错输出（V3：category 分类学，无 has_errors 字段）。

    has_errors 由 errors 派生，仅用于返回/入库，不要求大模型输出。
    """

    errors: list[ErrorBlock] = Field(default_factory=list)
    rewrite: RewriteSection

    @computed_field
    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


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

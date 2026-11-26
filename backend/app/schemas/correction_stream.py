import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CorrectionStreamRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    # 预留扩展：后续可以增加 revision / explain 等模式
    mode: Literal["correction"] = "correction"


class CorrectionRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: str
    source_text: str
    report: dict[str, Any]
    schema_version: int
    duration_ms: int | None
    model: str | None
    created_at: datetime


class CorrectionsResponse(BaseModel):
    corrections: list[CorrectionRecordOut]

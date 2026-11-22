from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    intent: Literal["correct", "followup"] | None = None
    turn_id: str | None = Field(default=None, pattern=r"^t\d+$")
    error_id: str | None = Field(default=None, pattern=r"^e\d+$")

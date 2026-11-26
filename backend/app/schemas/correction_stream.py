from typing import Literal

from pydantic import BaseModel, Field


class CorrectionStreamRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    # 预留扩展：后续可以增加 revision / explain 等模式
    mode: Literal["correction"] = "correction"

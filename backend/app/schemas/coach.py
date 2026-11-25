from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

MAX_USER_CHARS = 2000
MAX_ASSISTANT_CHARS = 40000
MAX_MESSAGES = 50


class CoachMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_length(self):
        limit = MAX_USER_CHARS if self.role == "user" else MAX_ASSISTANT_CHARS
        if len(self.content) > limit:
            raise ValueError(f"{self.role} content exceeds {limit} chars")
        return self


class CoachRequest(BaseModel):
    messages: list[CoachMessage] = Field(min_length=1, max_length=MAX_MESSAGES)

    @model_validator(mode="after")
    def _check_last_user(self):
        if self.messages[-1].role != "user":
            raise ValueError("last message must be from user")
        return self


class CoachError(BaseModel):
    severity: Literal["Critical", "Major", "Minor"]
    fragment: str
    type: str
    reason: str
    fix: str


class CoachRewrite(BaseModel):
    text: str
    note: str | None = None


class CoachRewrites(BaseModel):
    formal: CoachRewrite
    casual: CoachRewrite
    minimal: CoachRewrite


class CoachCorrection(BaseModel):
    """模型在纠错时输出的结构（无 mode / has_errors / learnings）。"""

    errors: list[CoachError]
    rewrites: CoachRewrites


class CoachCorrectReport(BaseModel):
    """服务端补全 mode / has_errors 后，用于 SSE 与前端渲染的报告。"""

    mode: Literal["correct"] = "correct"
    has_errors: bool = False
    errors: list[CoachError]
    rewrites: CoachRewrites

    @model_validator(mode="after")
    def _normalize_has_errors(self):
        self.has_errors = bool(self.errors)
        return self


class CoachAnswerReport(BaseModel):
    mode: Literal["answer"]
    answer: str


CoachReport = Annotated[
    Union[CoachCorrectReport, CoachAnswerReport],
    Field(discriminator="mode"),
]

from typing import Any, TypedDict


class CorrectionState(TypedDict, total=False):
    text: str
    request_id: str
    raw_errors: list[dict[str, Any]]
    errors: list[dict[str, str]]
    has_errors: bool
    minimal_text: str
    minimal_note: str
    fluency_text: str
    fluency_note: str
    minimal_error: str | None
    fluency_error: str | None

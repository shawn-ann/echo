from typing import Any, TypedDict


class TurnState(TypedDict, total=False):
    turn_id: str
    text: str
    errors: list[dict[str, Any]]
    minimal_text: str
    minimal_note: str
    fluency_text: str
    fluency_note: str


class CorrectionState(TypedDict, total=False):
    thread_id: str
    request_id: str
    content: str
    question: str
    hint_intent: str
    turn_id: str
    error_id: str
    rewrite_variant: str
    intent: str

    text: str
    raw_errors: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    has_errors: bool
    turns: list[TurnState]
    turn_seq: int
    current_turn_id: str

    resolution_status: str
    resolved_turn_id: str | None
    resolved_error_id: str | None
    resolved_variant: str | None
    candidate_refs: list[str]
    target_error: str | None

    minimal_text: str
    minimal_note: str
    fluency_text: str
    fluency_note: str
    minimal_error: str | None
    fluency_error: str | None

    explanation: str
    explanation_turn_id: str | None
    explanation_error_id: str | None
    explanation_focus: dict[str, Any] | None
    explanation_error: str | None

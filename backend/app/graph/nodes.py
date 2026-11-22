import json
import logging
import re
from typing import Any, Literal

from app.graph.state import CorrectionState
from app.prompts.explain_prompt import build_explain_messages
from app.prompts.locate_prompt import build_locate_messages
from app.prompts.rewrite_prompt import build_fluency_messages, build_minimal_messages
from app.services.error_validation import validate_errors
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

LOCATE_REASONING_EFFORT = "high"
REWRITE_REASONING_EFFORT = "low"
LOCATE_TEMPERATURE = 0.1
MINIMAL_TEMPERATURE = 0.1
FLUENCY_TEMPERATURE = 0.3


class LocateError(Exception):
    """定位节点在重试后仍无法返回可解析的错误列表。"""


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def make_locate_node(client: LLMClient):
    async def locate(state: CorrectionState) -> dict[str, Any]:
        messages = build_locate_messages(state["text"])
        last_error: Exception | None = None
        for _ in range(2):
            raw = await client.complete(
                messages,
                thinking=True,
                json_mode=True,
                reasoning_effort=LOCATE_REASONING_EFFORT,
                temperature=LOCATE_TEMPERATURE,
            )
            try:
                data = parse_json_object(raw)
                errors = data.get("errors")
                if not isinstance(errors, list):
                    raise ValueError("errors must be a list")
                return {"raw_errors": errors}
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                continue
        raise LocateError(str(last_error))

    return locate


def validate_errors_node(state: CorrectionState) -> dict[str, Any]:
    errors = validate_errors(
        state.get("raw_errors") or [],
        state["text"],
        request_id=state.get("request_id", "-"),
    )
    turn_id = state.get("current_turn_id") or state.get("turn_id") or "t1"
    turns = list(state.get("turns") or [])
    turns.append({"turn_id": turn_id, "text": state["text"], "errors": errors})
    turns = turns[-10:]
    return {
        "errors": errors,
        "has_errors": bool(errors),
        "current_turn_id": turn_id,
        "turns": turns,
    }


_CJK = re.compile(r"[\u4e00-\u9fff]")
_FOLLOWUP_MARKERS = re.compile(
    r"为什么|为.{0,3}么|为啥|为何|怎么|如何|解释|区别|哪个|是否|能不能|可以吗|"
    r"不用|还是|这个|这条|第.{1,3}个|更自然|换个说法|吗|呢"
)
_ENGLISH_START = re.compile(r"^\s*[A-Za-z]")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z']*")


def _looks_like_followup(content: str) -> bool:
    text = content.strip()
    if not text or len(text) > 200:
        return False
    if not _CJK.search(text):
        return False
    if _FOLLOWUP_MARKERS.search(text):
        return True
    # An English sentence with a Chinese word/note is a new correction request,
    # not a question about the previous one.
    if _ENGLISH_START.search(text) and len(_LATIN_WORD.findall(text)) >= 2:
        return False
    return True


def finalize_turn_node(state: CorrectionState) -> dict[str, Any]:
    turn_id = state.get("current_turn_id")
    turns = [dict(turn) for turn in (state.get("turns") or [])]
    for turn in turns:
        if turn.get("turn_id") == turn_id:
            turn.update(
                {
                    "minimal_text": state.get("minimal_text", ""),
                    "minimal_note": state.get("minimal_note", ""),
                    "fluency_text": state.get("fluency_text", ""),
                    "fluency_note": state.get("fluency_note", ""),
                }
            )
            break
    return {"turns": turns}


def route_node(state: CorrectionState) -> dict[str, Any]:
    content = state.get("content", "")
    hint = state.get("hint_intent")
    prior_turns = state.get("turns") or []
    prior_errors = state.get("errors") or []

    if hint in ("correct", "followup"):
        intent = hint
    elif state.get("turn_id") or state.get("error_id") or state.get("rewrite_variant"):
        intent = "followup"
    elif not prior_turns and not prior_errors and not state.get("turn_seq"):
        intent = "correct"
    elif _looks_like_followup(content):
        intent = "followup"
    else:
        intent = "correct"

    return {
        "intent": intent,
        "question": content if intent == "followup" else "",
    }


def _for_turn(turns: list[dict], turn_id: str) -> dict | None:
    return next((turn for turn in turns if turn.get("turn_id") == turn_id), None)


REWRITE_VARIANTS = ("minimal", "fluency", "both")


def _clean_variant(value: str | None) -> str | None:
    return value if value in REWRITE_VARIANTS else None


def _scope(
    status: str,
    *,
    turn_id: str | None = None,
    error_id: str | None = None,
    variant: str | None = None,
    target_error: str | None = None,
) -> dict[str, Any]:
    return {
        "resolution_status": status,
        "resolved_turn_id": turn_id,
        "resolved_error_id": error_id,
        "resolved_variant": variant,
        "candidate_refs": [],
        "target_error": target_error,
    }


def _missing_turn_error(state: CorrectionState, turn_id: str) -> str:
    turn_seq = state.get("turn_seq")
    if isinstance(turn_seq, int) and turn_seq > 0:
        try:
            seq = int(turn_id.lstrip("t"))
        except ValueError:
            seq = 0
        if seq and seq <= turn_seq - 10:
            return "历史已超出范围"
    return "找不到指定的轮次"


def resolve_target_node(state: CorrectionState) -> dict[str, Any]:
    """Resolve only deterministic references.

    Free-text refers to an error, a rewrite, or the whole turn are resolved by
    the explain model from the full turn data. Guessing here would silently
    override the user's intent, so code stays out of fuzzy matching.
    """
    turns = list(state.get("turns") or [])
    explicit_turn = state.get("turn_id") or None
    explicit_error = state.get("error_id") or None
    explicit_variant = _clean_variant(state.get("rewrite_variant"))

    if explicit_turn:
        turn = _for_turn(turns, explicit_turn)
        if not turn:
            return _scope(
                "none", target_error=_missing_turn_error(state, explicit_turn)
            )
        if explicit_error:
            if any(e.get("error_id") == explicit_error for e in turn.get("errors") or []):
                return _scope("direct", turn_id=explicit_turn, error_id=explicit_error)
            return _scope("none", target_error="找不到指定的错误条目")
        return _scope(
            "rewrite" if explicit_variant else "turn",
            turn_id=explicit_turn,
            variant=explicit_variant,
        )

    if explicit_error:
        for turn in turns:
            if any(e.get("error_id") == explicit_error for e in turn.get("errors") or []):
                return _scope("direct", turn_id=turn["turn_id"], error_id=explicit_error)
        return _scope("none", target_error="找不到指定的错误条目")

    if not turns:
        return _scope("none")

    if explicit_variant:
        return _scope(
            "rewrite", turn_id=turns[-1]["turn_id"], variant=explicit_variant
        )

    # Free text: hand every turn to the model, which knows how to read both
    # errors and rewrites. No regex guessing.
    return _scope("fuzzy")


def reset_correction_node(state: CorrectionState) -> dict[str, Any]:
    turn_seq = int(state.get("turn_seq") or 0) + 1
    return {
        "text": state.get("content", ""),
        "turn_seq": turn_seq,
        "current_turn_id": f"t{turn_seq}",
        "turn_id": "",
        "error_id": "",
        "rewrite_variant": "",
        "errors": [],
        "has_errors": False,
        "minimal_text": "",
        "minimal_note": "",
        "fluency_text": "",
        "fluency_note": "",
        "minimal_error": None,
        "fluency_error": None,
        "resolution_status": "",
        "resolved_turn_id": None,
        "resolved_error_id": None,
        "resolved_variant": None,
        "candidate_refs": [],
        "target_error": None,
        "explanation": "",
        "explanation_turn_id": None,
        "explanation_error_id": None,
        "explanation_focus": None,
        "explanation_error": None,
    }


def make_explain_node(client: LLMClient):
    async def explain(state: CorrectionState) -> dict[str, Any]:
        turns = list(state.get("turns") or [])
        if state.get("target_error"):
            return {"explanation_error": state["target_error"]}
        if not turns:
            return {"explanation_error": "没有可追问的错误"}

        status = state.get("resolution_status") or "none"
        selected_turn = state.get("resolved_turn_id")
        selected_error = state.get("resolved_error_id")
        selected_variant = state.get("resolved_variant")
        if status == "direct" and (
            not selected_turn
            or not selected_error
            or not _for_turn(turns, selected_turn)
            or not any(
                e.get("error_id") == selected_error
                for e in (_for_turn(turns, selected_turn) or {}).get("errors", [])
            )
        ):
            return {"explanation_error": "找不到指定的错误条目"}

        messages = build_explain_messages(
            turns,
            state.get("question") or "",
            selected_turn,
            selected_error,
            state.get("candidate_refs") or [],
            selected_variant,
        )
        try:
            raw = await client.complete(
                messages,
                thinking=True,
                json_mode=True,
                reasoning_effort="low",
                temperature=0.2,
            )
            data = parse_json_object(raw)
            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("explanation text must be non-empty")

            if status == "direct":
                # Explicit UI selection is authoritative.
                if data.get("turn_id") and data["turn_id"] != selected_turn:
                    return {"explanation_error": "解释结果与选定错误不一致"}
                if data.get("error_id") and data["error_id"] != selected_error:
                    return {"explanation_error": "解释结果与选定错误不一致"}
                out_turn = selected_turn
                out_error = selected_error
                out_variant = None
            elif status in ("turn", "rewrite"):
                # Explicit turn/variant: trust the user's scope over the model.
                out_turn = selected_turn or turns[-1]["turn_id"]
                out_error = data.get("error_id") or None
                out_variant = selected_variant
            else:
                # Free text: the model resolves the reference. Never reject the
                # answer because of a resolution mismatch; fall back and log.
                out_turn = data.get("turn_id") or selected_turn
                if not _for_turn(turns, out_turn):
                    if out_turn:
                        logger.warning(
                            "explain_unknown_turn request_id=%s turn_id=%s",
                            state.get("request_id", "-"),
                            out_turn,
                        )
                    out_turn = turns[-1]["turn_id"]
                out_error = data.get("error_id") or None
                out_variant = None

            out_turn_obj = _for_turn(turns, out_turn)
            if out_error and not any(
                e.get("error_id") == out_error
                for e in (out_turn_obj or {}).get("errors", [])
            ):
                logger.warning(
                    "explain_unknown_error request_id=%s turn_id=%s error_id=%s",
                    state.get("request_id", "-"),
                    out_turn,
                    out_error,
                )
                out_error = None

            focus = {
                "kind": "error" if out_error else ("rewrite" if out_variant else "turn"),
                "turn_id": out_turn,
                "error_id": out_error,
                "variant": out_variant,
            }
            return {
                "explanation": text,
                "explanation_turn_id": out_turn,
                "explanation_error_id": out_error,
                "explanation_focus": focus,
                "explanation_error": None,
            }
        except Exception:
            logger.exception(
                "explain_failed request_id=%s", state.get("request_id", "-")
            )
            return {"explanation_error": "解释生成失败"}

    return explain


def _parse_rewrite(raw: str) -> dict[str, str]:
    data = parse_json_object(raw)
    text = data.get("text")
    note = data.get("note")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("rewrite.text must be a non-empty string")
    if not isinstance(note, str):
        raise ValueError("rewrite.note must be a string")
    return {"text": text, "note": note}


def make_minimal_node(client: LLMClient):
    async def minimal(state: CorrectionState) -> dict[str, Any]:
        try:
            raw = await client.complete(
                build_minimal_messages(state["text"], state.get("errors") or []),
                thinking=False,
                json_mode=True,
                reasoning_effort=REWRITE_REASONING_EFFORT,
                temperature=MINIMAL_TEMPERATURE,
            )
            parsed = _parse_rewrite(raw)
            return {
                "minimal_text": parsed["text"],
                "minimal_note": parsed["note"],
                "minimal_error": None,
            }
        except Exception:
            logger.exception(
                "minimal_edit_failed request_id=%s", state.get("request_id", "-")
            )
            return {
                "minimal_text": "",
                "minimal_note": "",
                "minimal_error": "最小修正生成失败",
            }

    return minimal


def make_fluency_node(client: LLMClient):
    async def fluency(state: CorrectionState) -> dict[str, Any]:
        try:
            raw = await client.complete(
                build_fluency_messages(state["text"], state.get("errors") or []),
                thinking=False,
                json_mode=True,
                reasoning_effort=REWRITE_REASONING_EFFORT,
                temperature=FLUENCY_TEMPERATURE,
            )
            parsed = _parse_rewrite(raw)
            return {
                "fluency_text": parsed["text"],
                "fluency_note": parsed["note"],
                "fluency_error": None,
            }
        except Exception:
            logger.exception(
                "native_fluency_failed request_id=%s", state.get("request_id", "-")
            )
            return {
                "fluency_text": "",
                "fluency_note": "",
                "fluency_error": "地道表达生成失败",
            }

    return fluency


def minimal_passthrough_node(state: CorrectionState) -> dict[str, Any]:
    return {
        "minimal_text": state["text"],
        "minimal_note": "原文未发现语法错误，保持原样",
        "minimal_error": None,
    }


def route_after_validate(state: CorrectionState) -> Literal["minimal_edit", "minimal_passthrough"]:
    return "minimal_edit" if state.get("has_errors") else "minimal_passthrough"

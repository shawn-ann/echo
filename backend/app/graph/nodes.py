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
    if errors:
        turns.append({"turn_id": turn_id, "text": state["text"], "errors": errors})
        turns = turns[-10:]
    return {
        "errors": errors,
        "has_errors": bool(errors),
        "current_turn_id": turn_id,
        "turns": turns,
    }


_FOLLOWUP_MARKERS = re.compile(
    r"为什么|怎么|如何|解释|这个|这条|第.{1,3}个|有没有|更自然|换个说法|吗|呢|？|\?"
)
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _looks_like_followup(content: str) -> bool:
    text = content.strip()
    if not text or len(text) > 80:
        return False
    if not _CJK.search(text):
        return False
    return bool(_FOLLOWUP_MARKERS.search(text))


def route_node(state: CorrectionState) -> dict[str, Any]:
    content = state.get("content", "")
    hint = state.get("hint_intent")
    prior_turns = state.get("turns") or []
    prior_errors = state.get("errors") or []

    if hint in ("correct", "followup"):
        intent = hint
    elif state.get("turn_id") or state.get("error_id"):
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


def _token_hit(needle: str, query: str) -> bool:
    """Match whole tokens, so 'He' does not match 'she' and 'a' does not match 'an'."""
    value = needle.strip()
    if not value:
        return False
    pattern = rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])"
    return re.search(pattern, query, flags=re.IGNORECASE) is not None


def resolve_target_node(state: CorrectionState) -> dict[str, Any]:
    turns = list(state.get("turns") or [])
    question = state.get("content") or state.get("question") or ""
    explicit_turn = state.get("turn_id")
    explicit_error = state.get("error_id")

    if explicit_turn and explicit_error:
        turn = _for_turn(turns, explicit_turn)
        found = turn and any(e.get("error_id") == explicit_error for e in turn["errors"])
        if not found:
            target_error = "找不到指定的错误条目"
            turn_seq = state.get("turn_seq")
            if turn and not found:
                target_error = "找不到指定的错误条目"
            elif isinstance(turn_seq, int) and turn_seq > 10:
                try:
                    seq = int(explicit_turn.lstrip("t"))
                except ValueError:
                    seq = 0
                if seq and seq <= turn_seq - 10:
                    target_error = "历史已超出范围"
            return {
                "resolution_status": "none",
                "resolved_turn_id": None,
                "resolved_error_id": None,
                "candidate_refs": [],
                "target_error": target_error,
            }
        return {
            "resolution_status": "direct",
            "resolved_turn_id": explicit_turn,
            "resolved_error_id": explicit_error,
            "candidate_refs": [],
            "target_error": None,
        }

    if explicit_error:
        if turns:
            latest = turns[-1]
            if any(e.get("error_id") == explicit_error for e in latest["errors"]):
                return {
                    "resolution_status": "direct",
                    "resolved_turn_id": latest["turn_id"],
                    "resolved_error_id": explicit_error,
                    "candidate_refs": [],
                    "target_error": None,
                }
        return {
            "resolution_status": "none",
            "resolved_turn_id": None,
            "resolved_error_id": None,
            "candidate_refs": [],
            "target_error": "找不到指定的错误条目",
        }

    scoped_turns = [_for_turn(turns, explicit_turn)] if explicit_turn else turns
    scoped_turns = [turn for turn in scoped_turns if turn]
    query = question
    candidates: list[tuple[int, str, str]] = []

    for turn in reversed(scoped_turns):
        for error in turn.get("errors") or []:
            fragment = error.get("fragment") or ""
            correction = error.get("correction") or ""
            fragment_hit = _token_hit(fragment, query)
            correction_hit = _token_hit(correction, query)
            if not fragment_hit and not correction_hit:
                continue
            score = 2 if fragment_hit and correction_hit else 1
            candidates.append((score, turn["turn_id"], error["error_id"]))

    if not candidates:
        return {
            "resolution_status": "none",
            "resolved_turn_id": None,
            "resolved_error_id": None,
            "candidate_refs": [],
            "target_error": None,
        }

    pairs = [c for c in candidates if c[0] == 2]
    if len(pairs) == 1:
        _, turn_id, error_id = pairs[0]
        return {
            "resolution_status": "unique",
            "resolved_turn_id": turn_id,
            "resolved_error_id": error_id,
            "candidate_refs": [],
            "target_error": None,
        }
    if len(candidates) == 1:
        _, turn_id, error_id = candidates[0]
        return {
            "resolution_status": "unique",
            "resolved_turn_id": turn_id,
            "resolved_error_id": error_id,
            "candidate_refs": [],
            "target_error": None,
        }

    refs = [f"{turn_id}:{error_id}" for _, turn_id, error_id in candidates]
    return {
        "resolution_status": "ambiguous",
        "resolved_turn_id": None,
        "resolved_error_id": None,
        "candidate_refs": refs,
        "target_error": None,
    }


def reset_correction_node(state: CorrectionState) -> dict[str, Any]:
    turn_seq = int(state.get("turn_seq") or 0) + 1
    return {
        "text": state.get("content", ""),
        "turn_seq": turn_seq,
        "current_turn_id": f"t{turn_seq}",
        "turn_id": "",
        "error_id": "",
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
        "candidate_refs": [],
        "target_error": None,
        "explanation": "",
        "explanation_turn_id": None,
        "explanation_error_id": None,
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
        if status in ("direct", "unique") and (
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

            if status in ("direct", "unique"):
                if data.get("turn_id") and data["turn_id"] != selected_turn:
                    return {"explanation_error": "解释结果与选定错误不一致"}
                if data.get("error_id") and data["error_id"] != selected_error:
                    return {"explanation_error": "解释结果与选定错误不一致"}
                out_turn = selected_turn
                out_error = selected_error
            else:
                out_turn = data.get("turn_id") or selected_turn
                out_error = data.get("error_id") or selected_error
            out_turn_obj = _for_turn(turns, out_turn) if out_turn else None
            valid = bool(
                out_turn_obj
                and out_error
                and any(e.get("error_id") == out_error for e in out_turn_obj["errors"])
            )
            if not valid:
                return {"explanation_error": "无法确定你指的是哪一条错误"}

            return {
                "explanation": text,
                "explanation_turn_id": out_turn,
                "explanation_error_id": out_error,
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

"""错误条目应用侧校验：以 fragment 为准校正 span，并生成稳定 error_id。"""

import logging
from typing import Any

from app.prompts.taxonomy import CANONICAL_CATEGORIES

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = set(CANONICAL_CATEGORIES)


def _drop(request_id: str, reason: str, item: Any) -> None:
    logger.warning("drop_error request_id=%s reason=%s item=%r", request_id, reason, item)


def _positions(text: str, fragment: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(fragment, start)
        if index == -1:
            return positions
        positions.append(index)
        start = index + 1


def _choose_span(
    text: str,
    fragment: str,
    span_start: Any,
    span_end: Any,
    *,
    request_id: str,
) -> tuple[int, int] | None:
    length = len(fragment)
    if (
        isinstance(span_start, int)
        and isinstance(span_end, int)
        and 0 <= span_start < span_end <= len(text)
        and text[span_start:span_end] == fragment
    ):
        return span_start, span_start + length

    positions = _positions(text, fragment)
    if not positions:
        _drop(request_id, "fragment_not_in_text", fragment)
        return None
    if len(positions) == 1:
        return positions[0], positions[0] + length

    if not isinstance(span_start, int):
        _drop(request_id, "ambiguous_duplicate_without_span", fragment)
        return None

    distances = [abs(pos - span_start) for pos in positions]
    nearest = min(distances)
    threshold = max(2, length)
    winners = [pos for pos, dist in zip(positions, distances) if dist == nearest]
    if len(winners) != 1 or nearest > threshold:
        _drop(request_id, "ambiguous_duplicate_span", fragment)
        return None
    return winners[0], winners[0] + length


def validate_errors(
    raw_errors: Any,
    text: str,
    *,
    request_id: str = "-",
) -> list[dict[str, Any]]:
    """校验并清洗错误条目，返回带 error_id/span 的稳定列表。"""
    if not isinstance(raw_errors, list):
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str, str]] = set()

    for item in raw_errors:
        if not isinstance(item, dict):
            _drop(request_id, "not_a_dict", item)
            continue

        fragment = item.get("fragment")
        if not isinstance(fragment, str) or not fragment:
            _drop(request_id, "fragment_missing", item)
            continue
        if fragment not in text:
            _drop(request_id, "fragment_not_in_text", item)
            continue

        category = item.get("category")
        if category not in _ALLOWED_CATEGORIES:
            _drop(request_id, "category_not_allowed", item)
            continue

        correction = item.get("correction")
        if not isinstance(correction, str):
            _drop(request_id, "correction_missing", item)
            continue
        if correction and correction == fragment:
            _drop(request_id, "correction_noop", item)
            continue

        explanation = item.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            _drop(request_id, "explanation_missing", item)
            continue

        span = _choose_span(
            text,
            fragment,
            item.get("span_start"),
            item.get("span_end"),
            request_id=request_id,
        )
        if span is None:
            continue

        span_start, span_end = span
        key = (span_start, span_end, correction, category)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "category": category,
                "fragment": fragment,
                "correction": correction,
                "explanation": explanation,
                "span_start": span_start,
                "span_end": span_end,
            }
        )

    candidates.sort(key=lambda e: (e["span_start"], -e["span_end"]))

    kept: list[dict[str, Any]] = []
    for item in candidates:
        conflict_index = None
        for index, existing in enumerate(kept):
            if item["span_start"] < existing["span_end"] and existing["span_start"] < item["span_end"]:
                conflict_index = index
                break
        if conflict_index is None:
            kept.append(item)
            continue

        existing = kept[conflict_index]
        item_len = item["span_end"] - item["span_start"]
        existing_len = existing["span_end"] - existing["span_start"]
        if item_len > existing_len:
            logger.warning(
                "overlap_replaced request_id=%s kept=%r dropped=%r",
                request_id,
                item["fragment"],
                existing["fragment"],
            )
            kept[conflict_index] = item
        else:
            logger.warning(
                "overlap_dropped request_id=%s kept=%r dropped=%r",
                request_id,
                existing["fragment"],
                item["fragment"],
            )

    kept.sort(key=lambda e: (e["span_start"], -e["span_end"]))
    return [
        {"error_id": f"e{index}", **item}
        for index, item in enumerate(kept, start=1)
    ]

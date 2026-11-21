"""错误条目应用侧校验：只信任原文中真实存在的 fragment。"""

import logging
from typing import Any

from app.prompts.taxonomy import CANONICAL_CATEGORIES

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = set(CANONICAL_CATEGORIES)


def _drop(request_id: str, reason: str, item: Any) -> None:
    logger.warning("drop_error request_id=%s reason=%s item=%r", request_id, reason, item)


def validate_errors(
    raw_errors: Any,
    text: str,
    *,
    request_id: str = "-",
) -> list[dict[str, str]]:
    """校验并清洗 LLM 返回的错误条目。

    - fragment 必须是原文精确子串；找不到即丢弃（覆盖模型幻觉与偏移）。
    - category 必须是 38 类规范名之一。
    - correction 为空表示删除；非空时不得与 fragment 相同。
    - explanation 必须非空。
    - 按 (fragment, correction, category) 去重。
    """
    if not isinstance(raw_errors, list):
        return []

    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

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

        key = (fragment, correction, category)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "category": category,
                "fragment": fragment,
                "correction": correction,
                "explanation": explanation,
            }
        )

    return result

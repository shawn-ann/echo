"""验收断言纯函数：结构检查 + 语义检查。"""

from typing import Any

CATEGORY_ENUM = {"grammar", "collocation", "chinglish", "style"}


def _ci(text: str) -> str:
    return text.lower().replace("`", "")


def structure_check(report: dict[str, Any]) -> list[str]:
    """结构断言。返回失败消息列表；空列表 = 通过。"""
    failures: list[str] = []
    if not isinstance(report.get("has_errors"), bool):
        failures.append("has_errors 必须是布尔值")
    errors = report.get("errors")
    if not isinstance(errors, list):
        failures.append("errors 必须是数组")
        errors = []
    for i, e in enumerate(errors):
        for field in ("category", "error_type", "fragment", "explanation", "correction"):
            if not isinstance(e.get(field), str) or not e[field].strip():
                failures.append(f"errors[{i}].{field} 缺失或为空")
        if e.get("category") not in CATEGORY_ENUM:
            failures.append(f"errors[{i}].category 不在枚举内: {e.get('category')!r}")
    rewrite = report.get("rewrite")
    if not isinstance(rewrite, dict):
        failures.append("rewrite 必须是对象")
        rewrite = {}
    for key in ("minimal", "natural"):
        opt = rewrite.get(key)
        if not isinstance(opt, dict):
            failures.append(f"rewrite.{key} 缺失")
        else:
            for field in ("text", "explanation"):
                if not isinstance(opt.get(field), str):
                    failures.append(f"rewrite.{key}.{field} 缺失")
    learnings = report.get("learnings")
    if not isinstance(learnings, list):
        failures.append("learnings 必须是数组")
        learnings = []
    for i, l in enumerate(learnings):
        for field in ("title", "rule", "instances", "examples"):
            if field not in l:
                failures.append(f"learnings[{i}].{field} 缺失")
        if isinstance(l.get("instances"), list):
            for j, inst in enumerate(l["instances"]):
                if not isinstance(inst.get("wrong"), str) or not isinstance(inst.get("right"), str):
                    failures.append(f"learnings[{i}].instances[{j}] 需含 wrong/right")
    return failures


def _must_have_failure(must: dict[str, Any], errors: list[dict[str, Any]]) -> list[str]:
    """对一条 must_have 断言找失败：错误必须被识别（fragment 命中，忽略反引号/大小写）。

    不要求修正词精确匹配——措辞自由，只要求该错误被 LLM 识别出来（无遗漏）。
    """
    needle = _ci(must["fragment_contains"])
    for e in errors:
        if needle in _ci(e.get("fragment", "")):
            return []
    return [f"错误未识别: {must['fragment_contains']!r}"]


def semantic_check(report: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    """语义断言。返回失败消息列表；空列表 = 通过。"""
    failures: list[str] = []
    errors = report.get("errors") or []
    if report.get("has_errors") is not expect.get("has_errors"):
        failures.append(f"has_errors 期望 {expect.get('has_errors')}，实际 {report.get('has_errors')}")
    if len(errors) < expect.get("error_count_min", 0):
        failures.append(f"errors 数量 {len(errors)} < 期望 {expect.get('error_count_min')}")
    for must in expect.get("must_have", []):
        failures.extend(_must_have_failure(must, errors))
    # 每个错误必须有实质修正（correction 非空且与 fragment 不同），保证"改正合理"
    for i, e in enumerate(errors):
        corr = e.get("correction")
        frag = e.get("fragment")
        if not isinstance(corr, str) or not corr.strip():
            failures.append(f"errors[{i}].correction 缺失或为空")
        elif isinstance(frag, str) and _ci(corr) == _ci(frag):
            failures.append(f"errors[{i}].correction 与 fragment 相同（未实际修正）")
    full_text = _ci(
        str(report.get("rewrite", {}))
        + str(report.get("errors", []))
        + str(report.get("learnings", []))
    )
    for term in expect.get("preserve_terms", []):
        if _ci(term) not in full_text:
            failures.append(f"术语未保留: {term!r}")
    if len(report.get("learnings") or []) < expect.get("learnings_min", 0):
        failures.append(
            f"learnings 数量 {len(report.get('learnings') or [])} < 期望 {expect.get('learnings_min')}"
        )
    # 两版互异（仅当 has_errors=true；无错误时两版均为原句）
    rewrite = report.get("rewrite") or {}
    if report.get("has_errors") is True:
        if isinstance(rewrite.get("minimal"), dict) and isinstance(rewrite.get("natural"), dict):
            if rewrite["minimal"].get("text") == rewrite["natural"].get("text"):
                failures.append("minimal 与 natural 文本相同")
    return failures

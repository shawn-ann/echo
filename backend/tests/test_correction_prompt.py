import pytest

from app.prompts.correction_prompt import SYSTEM_PROMPT, build_system_prompt


def test_system_prompt_contains_contract_fields():
    assert "has_errors" in SYSTEM_PROMPT
    assert "error_type" in SYSTEM_PROMPT
    assert "fragment" in SYSTEM_PROMPT
    assert "explanation" in SYSTEM_PROMPT
    assert "correction" in SYSTEM_PROMPT
    assert "rewrite" in SYSTEM_PROMPT
    assert "learnings" not in SYSTEM_PROMPT
    assert "minimal" in SYSTEM_PROMPT
    assert "natural" in SYSTEM_PROMPT
    assert "note" in SYSTEM_PROMPT


def test_system_prompt_removed_contract_fields():
    assert "intent" not in SYSTEM_PROMPT
    assert "category" not in SYSTEM_PROMPT
    # 输出字段列表不包含顶层 reply（示例中的 reply 一词不在此列）
    assert "- reply（" not in SYSTEM_PROMPT
    assert "## 意图判定" not in SYSTEM_PROMPT


def test_system_prompt_has_check_rules():
    for section in ("冠词缺失", "编程标识符", "主谓一致", "单复数", "动词形式", "词性误用",
                    "词序不当", "介词搭配", "搭配不当", "搭配冗余", "口语正常表达", "粒度要求"):
        assert section in SYSTEM_PROMPT


def test_system_prompt_no_markdown_fence():
    assert "```" not in SYSTEM_PROMPT


def test_system_prompt_no_old_learnings_fields():
    # 旧 learnings 四字段契约已移除
    assert "instances" not in SYSTEM_PROMPT
    assert "title" not in SYSTEM_PROMPT


def test_build_system_prompt_styles_return_same():
    casual = build_system_prompt("casual")
    formal = build_system_prompt("formal")
    assert casual == formal  # 当前固定返回新提示词，暂不支持切换


def test_build_system_prompt_invalid_style():
    with pytest.raises(ValueError):
        build_system_prompt("bogus")


def test_system_prompt_default_is_casual():
    assert SYSTEM_PROMPT == build_system_prompt("casual")

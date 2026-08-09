import pytest

from app.prompts.correction_prompt import SYSTEM_PROMPT, build_system_prompt


def test_system_prompt_contains_contract_fields():
    assert "intent" in SYSTEM_PROMPT
    assert "correction" in SYSTEM_PROMPT
    assert "reply" in SYSTEM_PROMPT
    assert "category" in SYSTEM_PROMPT
    assert "error_type" in SYSTEM_PROMPT
    assert "learnings" in SYSTEM_PROMPT
    assert "minimal" in SYSTEM_PROMPT
    assert "natural" in SYSTEM_PROMPT


def test_system_prompt_contains_enum_values():
    for v in ("grammar", "collocation", "chinglish", "style"):
        assert v in SYSTEM_PROMPT
    for v in ("Major", "Minor"):
        assert v not in SYSTEM_PROMPT  # 契约不加 severity


def test_system_prompt_no_markdown_fence():
    assert "```" not in SYSTEM_PROMPT


def test_system_prompt_requires_paired_examples():
    assert "examples" in SYSTEM_PROMPT
    assert '"wrong"' in SYSTEM_PROMPT
    assert '"right"' in SYSTEM_PROMPT


def test_system_prompt_no_error_rewrite_empty():
    assert "text 均为空字符串" in SYSTEM_PROMPT


def test_build_system_prompt_casual_vs_formal():
    casual = build_system_prompt("casual")
    formal = build_system_prompt("formal")
    assert casual != formal
    # casual：口语场景 + 口语省略不判错
    assert "日常/职场口语场景" in casual
    assert "不列为修正项" in casual
    assert "getting an error" in casual
    # formal：正式书面 + 补全省略疑问句
    assert "正式书面场景" in formal
    assert "补全为书面完整形式" in formal
    # 两 style 都保留核心契约字段
    for field in ("intent", "correction", "reply", "category", "error_type", "learnings", "minimal", "natural"):
        assert field in casual and field in formal


def test_build_system_prompt_invalid_style():
    with pytest.raises(ValueError):
        build_system_prompt("bogus")


def test_system_prompt_default_is_casual():
    assert SYSTEM_PROMPT == build_system_prompt("casual")

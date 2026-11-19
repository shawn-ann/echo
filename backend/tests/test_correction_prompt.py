import pytest

from app.prompts.correction_prompt import SYSTEM_PROMPT, build_system_prompt


def test_system_prompt_contains_new_contract_fields():
    for token in ("category", "fragment", "correction", "explanation", "rewrite", "minimal", "natural", "note"):
        assert token in SYSTEM_PROMPT


def test_system_prompt_removed_old_contract_fields():
    assert "error_type" not in SYSTEM_PROMPT
    assert "has_errors" not in SYSTEM_PROMPT
    assert "{{input}}" not in SYSTEM_PROMPT
    assert "=== USER INPUT ===" not in SYSTEM_PROMPT
    assert "learnings" not in SYSTEM_PROMPT


def test_system_prompt_contains_taxonomy_and_boundaries():
    for section in ("CANONICAL LIST", "JUDGMENT BOUNDARIES", "OUT OF SCOPE", "HARD RULES", "REWRITE RULES"):
        assert section in SYSTEM_PROMPT


def test_system_prompt_has_no_out_of_list_category_names():
    # 规则里只能引用词表内的类别名
    assert "语域错配" not in SYSTEM_PROMPT
    assert "表达不地道" not in SYSTEM_PROMPT


def test_catchall_requires_unacceptability_not_preference():
    # 兜底类不能因“存在别的说法”就触发
    assert "would phrase it differently" not in SYSTEM_PROMPT
    assert "NO competent native writer would produce this phrasing" in SYSTEM_PROMPT


def test_correction_must_be_smallest_edit():
    assert "smallest edit" in SYSTEM_PROMPT
    assert "Do not bundle unrelated dimensions into one correction" in SYSTEM_PROMPT


def test_overlapping_fragments_rule_present():
    assert "If two reported fragments overlap" in SYSTEM_PROMPT


def test_system_prompt_no_markdown_fence():
    assert "```" not in SYSTEM_PROMPT


def test_build_system_prompt_styles_return_same():
    assert build_system_prompt("casual") == build_system_prompt("formal")


def test_build_system_prompt_invalid_style():
    with pytest.raises(ValueError):
        build_system_prompt("bogus")


def test_system_prompt_default_is_casual():
    assert SYSTEM_PROMPT == build_system_prompt("casual")

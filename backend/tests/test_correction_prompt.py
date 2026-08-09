from app.prompts.correction_prompt import SYSTEM_PROMPT


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
    assert "成对的" in SYSTEM_PROMPT
    assert "错误句" in SYSTEM_PROMPT
    assert "孤立的" in SYSTEM_PROMPT

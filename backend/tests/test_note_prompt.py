from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content


def test_system_prompt_contains_granularity_rules():
    prompt = build_note_system_prompt(existing_rules=[])
    assert "可单独测试的规则点" in prompt
    assert "介词后加 -ing 形式" in prompt
    assert "过去时" in prompt  # 反例
    assert "原样返回" in prompt  # 去重指令


def test_system_prompt_includes_existing_rules():
    prompt = build_note_system_prompt(existing_rules=["介词后加 -ing 形式", "to 不定式接原形"])
    assert "介词后加 -ing 形式" in prompt
    assert "to 不定式接原形" in prompt


def test_user_content_contains_source_and_errors():
    content = build_note_user_content(
        source_text="I interested in read",
        errors=[{"error_type": "动词形式", "fragment": "interested in read", "explanation": "介词后加 ing", "correction": "interested in reading"}],
    )
    assert "I interested in read" in content
    assert "interested in read" in content
    assert "interested in reading" in content

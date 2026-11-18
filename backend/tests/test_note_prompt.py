from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content


def test_system_prompt_contains_8field_fields():
    prompt = build_note_system_prompt()
    assert "rule_title" in prompt
    assert "knowledge_point" in prompt
    assert "warning" not in prompt
    assert "alternatives" in prompt
    assert "feynman_question" in prompt
    assert "error_root" in prompt
    assert "change_details" in prompt


def test_system_prompt_group_by_category():
    prompt = build_note_system_prompt()
    assert "category" in prompt
    assert "error_type" not in prompt
    assert "合并" in prompt
    assert "1 个元素" in prompt


def test_system_prompt_no_dedup():
    prompt = build_note_system_prompt()
    assert "已有规则" not in prompt


def test_system_prompt_alternatives_distinct():
    """alternatives 应要求各条明显不同，禁止仅标点/大小写差异的近重复"""
    prompt = build_note_system_prompt()
    assert "明显不同" in prompt
    assert "标点" in prompt
    assert "大小写" in prompt


def test_user_content_contains_source_and_errors():
    content = build_note_user_content(
        source_text="She go to school. He go home.",
        errors=[
            {"category": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"},
            {"category": "主谓不一致", "fragment": "He go", "explanation": "x", "correction": "He goes"},
        ],
    )
    assert "She go to school. He go home." in content
    assert "She go" in content
    assert "She goes" in content
    assert "主谓不一致" in content

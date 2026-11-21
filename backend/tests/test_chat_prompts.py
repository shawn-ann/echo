from app.prompts.locate_prompt import build_locate_messages
from app.prompts.rewrite_prompt import build_fluency_messages, build_minimal_messages


def test_locate_prompt_has_taxonomy_and_data_boundary():
    messages = build_locate_messages("Yesterday I go to school.")
    assert "TASK: LOCATE_ERRORS" in messages[0]["content"]
    assert "时态错误" in messages[0]["content"]
    assert "技术术语误用" in messages[0]["content"]
    assert '"fragment"' in messages[0]["content"]
    assert "---BEGIN DATA---" in messages[1]["content"]
    assert "Yesterday I go to school." in messages[1]["content"]


def test_minimal_prompt_has_marker_and_errors():
    errors = [{"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "x"}]
    messages = build_minimal_messages("Yesterday I go to school.", errors)
    assert "TASK: MINIMAL_EDIT" in messages[0]["content"]
    assert "---BEGIN DATA---" in messages[1]["content"]
    assert '"fragment": "go"' in messages[1]["content"]


def test_fluency_prompt_accepts_empty_errors():
    messages = build_fluency_messages("Hello.", [])
    assert "TASK: NATIVE_FLUENCY" in messages[0]["content"]
    assert '"errors": []' in messages[1]["content"]

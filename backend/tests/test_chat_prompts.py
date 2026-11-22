from app.prompts.explain_prompt import build_explain_messages
from app.prompts.locate_prompt import build_locate_messages
from app.prompts.rewrite_prompt import build_fluency_messages, build_minimal_messages


def test_locate_prompt_has_taxonomy_and_data_boundary():
    messages = build_locate_messages("Yesterday I go to school.")
    assert "TASK: LOCATE_ERRORS" in messages[0]["content"]
    assert "时态错误" in messages[0]["content"]
    assert "技术术语误用" in messages[0]["content"]
    assert '"fragment"' in messages[0]["content"]
    assert '"span_start"' in messages[0]["content"]
    assert '"span_end"' in messages[0]["content"]
    assert "JUDGMENT BOUNDARIES" in messages[0]["content"]
    assert "Classify every error by what the minimal fix changes" in messages[0]["content"]
    assert "OUT OF SCOPE" in messages[0]["content"]
    assert "Capitalization" in messages[0]["content"]
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


def test_explain_prompt_contains_history_and_target():
    turns = [{"turn_id": "t1", "text": "I go.", "errors": [{"error_id": "e1"}]}]
    messages = build_explain_messages(turns, "为什么 go 改成 went？", "t1", "e1")
    assert "TASK: EXPLAIN_ERROR" in messages[0]["content"]
    assert '"turn_id": "t1"' in messages[1]["content"]
    assert '"error_id": "e1"' in messages[1]["content"]
    assert "为什么 go 改成 went？" in messages[1]["content"]


def test_explain_prompt_mentions_rewrites_and_turn_scope():
    messages = build_explain_messages([], "q", "t1", None, variant="both")
    system = messages[0]["content"]
    assert "minimal_text" in system
    assert "fluency_text" in system
    assert "selected_error_id" in system
    assert "omitted" in system.lower()
    assert '"selected_variant": "both"' in messages[1]["content"]


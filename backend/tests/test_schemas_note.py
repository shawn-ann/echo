import pytest
from pydantic import ValidationError

from app.schemas.note import UpdateNoteRequest


def test_update_note_request_valid():
    payload = UpdateNoteRequest(
        rule_title="标题",
        knowledge_point="知识点",
        alternatives=["A", "B"],
        feynman_question="费曼",
    )
    assert payload.rule_title == "标题"
    assert payload.alternatives == ["A", "B"]


def test_update_note_request_alternatives_can_be_empty():
    payload = UpdateNoteRequest(
        rule_title="标题",
        knowledge_point="知识点",
        alternatives=[],
        feynman_question="费曼",
    )
    assert payload.alternatives == []


@pytest.mark.parametrize("field", ["rule_title", "knowledge_point", "feynman_question"])
def test_update_note_request_text_fields_required(field):
    data = {
        "rule_title": "t",
        "knowledge_point": "k",
        "alternatives": [],
        "feynman_question": "f",
    }
    data[field] = ""
    with pytest.raises(ValidationError):
        UpdateNoteRequest(**data)

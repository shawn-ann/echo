import json

from app.services.partial_json import parse_partial


def test_parse_complete_json():
    result = parse_partial('{"mode":"correct","keep":true}')
    assert result is not None
    assert result.complete
    assert result.value["mode"].value == "correct"
    assert result.value["keep"].value is True


def test_partial_string_is_marked_incomplete():
    result = parse_partial('{"mode":"corr')
    assert result is not None
    assert result.value["mode"].value == "corr"
    assert result.value["mode"].complete is False


def test_escaped_strings_are_decoded():
    raw = json.dumps({"answer": "第一段\n第二段 \"quote\""})
    result = parse_partial(raw)
    assert result is not None
    assert result.value["answer"].value == "第一段\n第二段 \"quote\""


def test_array_only_keeps_complete_items():
    raw = '[{"a":1},{"a":2},{"a":'
    result = parse_partial(raw)
    assert result is not None
    assert result.complete is False
    assert [item.value["a"].value for item in result.value] == [1, 2]


def test_nested_object_stops_at_incomplete_value():
    raw = '{"errors":[{"severity":"Major","fragment":"go","type":"时态错误","reason":"x","fix":"wen'
    result = parse_partial(raw)
    assert result is not None
    errors = result.value["errors"].value
    assert errors == []


def test_garbage_returns_none_or_incomplete():
    assert parse_partial("") is None
    result = parse_partial("not json")
    assert result is None or not result.complete

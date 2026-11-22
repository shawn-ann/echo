from app.services.error_validation import validate_errors

TEXT = "Yesterday I go to school."


def test_accepts_valid_item():
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "过去时间用过去式"}]
    start = TEXT.index("go")
    assert validate_errors(raw, TEXT) == [
        {
            "error_id": "e1",
            "category": "时态错误",
            "fragment": "go",
            "correction": "went",
            "explanation": "过去时间用过去式",
            "span_start": start,
            "span_end": start + len("go"),
        }
    ]


def test_unique_fragment_gets_span_and_error_id():
    raw = [{
        "category": "时态错误", "fragment": "go", "correction": "went",
        "explanation": "x", "span_start": 0, "span_end": 0,
    }]
    start = TEXT.index("go")
    assert validate_errors(raw, TEXT) == [{
        "error_id": "e1", "category": "时态错误", "fragment": "go",
        "correction": "went", "explanation": "x",
        "span_start": start, "span_end": start + 2,
    }]


def test_missing_span_uses_unique_fragment():
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "x"}]
    assert validate_errors(raw, TEXT)[0]["error_id"] == "e1"


def test_drops_hallucinated_fragment():
    raw = [{"category": "时态错误", "fragment": "goes", "correction": "went", "explanation": "x"}]
    assert validate_errors(raw, TEXT) == []


def test_drops_unknown_category():
    raw = [{"category": "grammar", "fragment": "go", "correction": "went", "explanation": "x"}]
    assert validate_errors(raw, TEXT) == []


def test_allows_deletion_and_rejects_noop():
    start = "I very like it.".index(" very")
    assert validate_errors(
        [{"category": "冗余啰嗦", "fragment": " very", "correction": "", "explanation": "删除"}],
        "I very like it.",
    ) == [{
        "error_id": "e1",
        "category": "冗余啰嗦",
        "fragment": " very",
        "correction": "",
        "explanation": "删除",
        "span_start": start,
        "span_end": start + len(" very"),
    }]
    assert validate_errors(
        [{"category": "时态错误", "fragment": "go", "correction": "go", "explanation": "x"}],
        TEXT,
    ) == []


def test_dedupes_same_fix_and_drops_conflicting_same_span():
    same = {"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "x"}
    other = {"category": "主谓不一致", "fragment": "go", "correction": "goes", "explanation": "y"}
    assert len(validate_errors([same, same], TEXT)) == 1
    assert len(validate_errors([same, other], TEXT)) == 1


def test_keeps_distinct_spans():
    text = "I go now and I go later."
    first = text.index("go")
    second = text.index("go", first + 1)
    raw = [
        {"category": "时态错误", "fragment": "go", "correction": "went",
         "explanation": "x", "span_start": first, "span_end": first + 2},
        {"category": "时态错误", "fragment": "go", "correction": "went",
         "explanation": "x", "span_start": second, "span_end": second + 2},
    ]
    result = validate_errors(raw, text)
    assert [e["span_start"] for e in result] == [first, second]
    assert [e["error_id"] for e in result] == ["e1", "e2"]


def test_duplicate_fragment_uses_span_hint():
    text = "I go now and I go later."
    second = text.index("go", text.index("go") + 1)
    raw = [{
        "category": "时态错误", "fragment": "go", "correction": "went",
        "explanation": "x", "span_start": second, "span_end": second + 2,
    }]
    result = validate_errors(raw, text)
    assert result[0]["span_start"] == second


def test_duplicate_fragment_without_span_is_dropped():
    text = "I go now and I go later."
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "x"}]
    assert validate_errors(raw, text) == []


def test_overlap_keeps_larger_span():
    text = "She go to school yesterday."
    raw = [
        {"category": "时态错误", "fragment": "She go to school yesterday",
         "correction": "She went to school yesterday", "explanation": "x",
         "span_start": 0, "span_end": len("She go to school yesterday")},
        {"category": "主谓不一致", "fragment": "She go",
         "correction": "She goes", "explanation": "y", "span_start": 0, "span_end": 6},
    ]
    result = validate_errors(raw, text)
    assert len(result) == 1
    assert result[0]["fragment"] == "She go to school yesterday"


def test_emoji_span_uses_python_codepoints():
    text = "I 😀 go now."
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "x"}]
    start = text.index("go")
    assert validate_errors(raw, text)[0]["span_start"] == start


def test_empty_and_malformed_input_returns_empty():
    assert validate_errors(None, TEXT) == []
    assert validate_errors([], TEXT) == []
    assert validate_errors(["not-a-dict"], TEXT) == []

from app.services.error_validation import validate_errors

TEXT = "Yesterday I go to school."


def test_accepts_valid_item():
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "过去时间用过去式"}]
    assert validate_errors(raw, TEXT) == raw


def test_drops_hallucinated_fragment():
    raw = [{"category": "时态错误", "fragment": "goes", "correction": "went", "explanation": "x"}]
    assert validate_errors(raw, TEXT) == []


def test_drops_unknown_category():
    raw = [{"category": "grammar", "fragment": "go", "correction": "went", "explanation": "x"}]
    assert validate_errors(raw, TEXT) == []


def test_allows_deletion_and_rejects_noop():
    assert validate_errors(
        [{"category": "冗余啰嗦", "fragment": " very", "correction": "", "explanation": "删除"}],
        "I very like it.",
    ) == [{"category": "冗余啰嗦", "fragment": " very", "correction": "", "explanation": "删除"}]
    assert validate_errors(
        [{"category": "时态错误", "fragment": "go", "correction": "go", "explanation": "x"}],
        TEXT,
    ) == []


def test_dedupes_same_fix_and_keeps_distinct_fixes():
    same = {"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "x"}
    other = {"category": "主谓不一致", "fragment": "go", "correction": "goes", "explanation": "y"}
    assert validate_errors([same, same], TEXT) == [same]
    assert validate_errors([same, other], TEXT) == [same, other]


def test_empty_and_malformed_input_returns_empty():
    assert validate_errors(None, TEXT) == []
    assert validate_errors([], TEXT) == []
    assert validate_errors(["not-a-dict"], TEXT) == []

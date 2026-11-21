from app.prompts.taxonomy import CANONICAL_CATEGORIES


def test_canonical_categories_are_complete_and_unique():
    assert len(CANONICAL_CATEGORIES) == 38
    assert len(set(CANONICAL_CATEGORIES)) == 38
    assert CANONICAL_CATEGORIES[0] == "时态错误"
    assert "拼写错误" in CANONICAL_CATEGORIES
    assert "技术术语误用" in CANONICAL_CATEGORIES

from app.prompts.golden_cases import load_golden_cases


def test_load_returns_9_cases():
    cases = load_golden_cases()
    assert len(cases) == 9


def test_each_case_has_required_keys():
    for case in load_golden_cases():
        assert set(("id", "input", "expect")).issubset(case.keys())
        assert isinstance(case["id"], str)
        assert isinstance(case["input"], str)
        assert isinstance(case["expect"], dict)


def test_all_cases_have_unique_ids():
    ids = [c["id"] for c in load_golden_cases()]
    assert len(ids) == len(set(ids))


def test_expect_sub_schema():
    expect_keys = {"has_errors", "error_count_min", "must_have", "preserve_terms", "learnings_min"}
    must_keys = {"fragment_contains"}
    for case in load_golden_cases():
        expect = case["expect"]
        assert expect_keys.issubset(expect.keys()), f"{case['id']} expect 缺字段"
        assert isinstance(expect["has_errors"], bool)
        assert isinstance(expect["error_count_min"], int)
        assert isinstance(expect["must_have"], list)
        assert isinstance(expect["preserve_terms"], list)
        assert isinstance(expect["learnings_min"], int)
        for must in expect["must_have"]:
            assert must_keys.issubset(must.keys()), f"{case['id']} must_have 缺字段"
            assert isinstance(must["fragment_contains"], str)

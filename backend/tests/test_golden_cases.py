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
    must_keys = {"fragment_contains"}
    for case in load_golden_cases():
        expect = case["expect"]
        assert isinstance(expect["has_errors"], bool), f"{case['id']} has_errors 应为 bool"
        if expect["has_errors"] is True:
            assert "must_have" in expect, f"{case['id']} has_errors=true 需 must_have"
            assert isinstance(expect["must_have"], list)
            for must in expect["must_have"]:
                assert must_keys.issubset(must.keys()), f"{case['id']} must_have 缺字段"
                assert isinstance(must["fragment_contains"], str)
        else:
            assert "must_have" not in expect, f"{case['id']} has_errors=false 不应有 must_have"

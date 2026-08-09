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

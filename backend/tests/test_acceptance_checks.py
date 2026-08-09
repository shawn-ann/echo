from app.scripts.acceptance_checks import (
    CATEGORY_ENUM,
    structure_check,
    semantic_check,
)


def _valid_report():
    return {
        "has_errors": True,
        "errors": [
            {
                "category": "grammar",
                "error_type": "冠词缺失",
                "fragment": "creating job",
                "explanation": "job 是可数名词单数",
                "correction": "creating a job",
            }
        ],
        "rewrite": {
            "minimal": {"text": "Correct the trigger_by field setup logic when creating a job.", "explanation": "仅修正语法和用词"},
            "natural": {"text": "Fix the trigger_by field setup logic when creating a job.", "explanation": "更自然"},
        },
        "learnings": [
            {
                "title": "可数名词单数不能裸用",
                "rule": "可数名词单数必须加冠词",
                "instances": [{"wrong": "creating job", "right": "creating a job"}],
                "examples": ["I'm deploying service ❌ → I'm deploying a service ✅"],
            }
        ],
    }


def test_structure_check_valid():
    errors = structure_check(_valid_report())
    assert errors == []


def test_structure_check_missing_category():
    report = _valid_report()
    report["errors"][0]["category"] = "typo"
    errors = structure_check(report)
    assert any("category" in e for e in errors)


def test_structure_check_missing_field():
    report = _valid_report()
    del report["errors"][0]["correction"]
    errors = structure_check(report)
    assert any("correction" in e for e in errors)


def test_structure_check_rewrite_needs_both():
    report = _valid_report()
    del report["rewrite"]["natural"]
    errors = structure_check(report)
    assert any("natural" in e for e in errors)


def test_structure_check_learnings_required_fields():
    report = _valid_report()
    del report["learnings"][0]["examples"]
    errors = structure_check(report)
    assert any("examples" in e for e in errors)


def test_semantic_check_hit_and_miss():
    expect = {
        "has_errors": True,
        "error_count_min": 1,
        "must_have": [
            {"fragment_contains": "creating job"}
        ],
        "preserve_terms": ["trigger_by"],
        "learnings_min": 1,
    }
    # 满足期望的响应 → 无失败
    failures = semantic_check(_valid_report(), expect)
    assert failures == []
    # 错误未被识别（fragment 未命中）→ 失败
    bad = _valid_report()
    bad["errors"][0]["fragment"] = "unrelated fragment here"
    failures = semantic_check(bad, expect)
    assert any("错误未识别" in f for f in failures)


def test_semantic_check_no_real_fix():
    """correction 与 fragment 相同（未实际修正）→ 失败。"""
    expect = {"has_errors": True, "error_count_min": 1, "must_have": [], "preserve_terms": [], "learnings_min": 0}
    report = _valid_report()
    report["errors"][0]["fragment"] = "creating job"
    report["errors"][0]["correction"] = "creating job"
    failures = semantic_check(report, expect)
    assert any("未实际修正" in f for f in failures)


def test_semantic_check_perfect_case():
    report = {
        "has_errors": False,
        "errors": [],
        "rewrite": {
            "minimal": {"text": "I'll check the logs.", "explanation": ""},
            "natural": {"text": "I'll check the logs.", "explanation": ""},
        },
        "learnings": [],
    }
    expect = {"has_errors": False, "error_count_min": 0, "must_have": [], "preserve_terms": [], "learnings_min": 0}
    assert semantic_check(report, expect) == []


def test_semantic_check_case_insensitive_and_backtick():
    expect = {"has_errors": True, "error_count_min": 1,
              "must_have": [{"fragment_contains": "triggering dag"}],
              "preserve_terms": [], "learnings_min": 1}
    report = _valid_report()
    report["errors"][0] = {
        "category": "grammar", "error_type": "冠词缺失", "fragment": "when triggering `dag`",
        "explanation": "x", "correction": "triggering the `DAG`",
    }
    report["rewrite"]["minimal"] = {"text": "... a dag ...", "explanation": ""}
    assert semantic_check(report, expect) == []

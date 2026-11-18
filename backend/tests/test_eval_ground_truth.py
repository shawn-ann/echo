from app.scripts.eval_ground_truth import _model_category


def test_model_category_prefers_new_field():
    assert _model_category({"category": "冠词缺失", "error_type": "旧值"}) == "冠词缺失"


def test_model_category_falls_back_to_legacy_field():
    assert _model_category({"error_type": "词序不当"}) == "词序不当"


def test_model_category_missing_returns_empty():
    assert _model_category({}) == ""

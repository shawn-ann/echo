import pytest
from pydantic import ValidationError

from app.schemas.correction import CorrectionBody, SubmitRequest

REWRITE = {
    "minimal": {"text": "a", "note": "n1"},
    "natural": {"text": "b", "note": "n2"},
}


def test_correction_body_valid_with_category():
    parsed = CorrectionBody.model_validate(
        {
            "errors": [
                {"category": "时态错误", "fragment": "I go to", "explanation": "x", "correction": "I went to"}
            ],
            "rewrite": REWRITE,
        }
    )
    assert parsed.has_errors is True
    assert parsed.errors[0].category == "时态错误"
    assert parsed.rewrite.minimal.note == "n1"


def test_correction_body_no_errors_derives_has_errors_false():
    parsed = CorrectionBody.model_validate({"errors": [], "rewrite": REWRITE})
    assert parsed.has_errors is False
    assert parsed.model_dump()["has_errors"] is False


def test_correction_body_missing_category_rejected():
    with pytest.raises(ValidationError):
        CorrectionBody.model_validate(
            {"errors": [{"fragment": "a", "explanation": "b", "correction": "c"}], "rewrite": REWRITE}
        )


def test_correction_body_missing_rewrite_rejected():
    with pytest.raises(ValidationError):
        CorrectionBody.model_validate({"errors": []})


def test_correction_body_ignores_model_supplied_has_errors():
    # 模型即使多输出 has_errors，也以 errors 为准
    parsed = CorrectionBody.model_validate({"has_errors": False, "errors": [], "rewrite": REWRITE})
    assert parsed.has_errors is False


def test_correction_body_model_dump_matches_contract():
    body = CorrectionBody(
        errors=[{"category": "冠词缺失", "fragment": "job", "explanation": "x", "correction": "a job"}],
        rewrite=REWRITE,
    )
    dumped = body.model_dump()
    assert dumped["has_errors"] is True
    assert "category" in dumped["errors"][0]
    assert "error_type" not in dumped["errors"][0]
    assert dumped["rewrite"]["minimal"]["text"] == "a"


def test_submit_request_length_boundaries():
    assert SubmitRequest(content="a").content == "a"
    assert SubmitRequest(content="x" * 2000).content == "x" * 2000
    with pytest.raises(ValidationError):
        SubmitRequest(content="")
    with pytest.raises(ValidationError):
        SubmitRequest(content="x" * 2001)

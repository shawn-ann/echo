import json

import pytest
from pydantic import ValidationError

from app.schemas.correction import CorrectionBody, SubmitRequest


def test_correction_body_valid():
    payload = {
        "has_errors": True,
        "errors": [{"error_type": "时态错误", "fragment": "I go to", "explanation": "x", "correction": "I went to"}],
        "rewrite": {"minimal": {"text": "a", "note": "n1"}, "natural": {"text": "b", "note": "n2"}},
    }
    parsed = CorrectionBody.model_validate(payload)
    assert parsed.has_errors is True
    assert parsed.errors[0].error_type == "时态错误"
    assert parsed.rewrite.minimal.note == "n1"


def test_correction_body_no_error_rewrite_null():
    parsed = CorrectionBody.model_validate({"has_errors": False, "errors": [], "rewrite": None})
    assert parsed.has_errors is False
    assert parsed.rewrite is None


def test_correction_body_missing_error_type_rejected():
    with pytest.raises(ValidationError):
        CorrectionBody.model_validate(
            {"has_errors": True, "errors": [{"fragment": "a", "explanation": "b", "correction": "c"}]}
        )


def test_correction_body_ignores_legacy_category():
    # 新契约移除 category：LLM 若仍输出 category 会被忽略，不影响解析
    parsed = CorrectionBody.model_validate(
        {"has_errors": True, "errors": [{"category": "grammar", "error_type": "x", "fragment": "a", "explanation": "b", "correction": "c"}]}
    )
    assert parsed.errors[0].error_type == "x"


def test_correction_body_model_dump_matches_contract():
    body = CorrectionBody(
        has_errors=True,
        errors=[{"error_type": "冠词缺失", "fragment": "job", "explanation": "x", "correction": "a job"}],
        rewrite=None,
    )
    dumped = body.model_dump()
    assert "error_type" in dumped["errors"][0]
    assert "category" not in dumped["errors"][0]
    assert dumped["rewrite"] is None


def test_submit_request_length_boundaries():
    assert SubmitRequest(content="a").content == "a"
    assert SubmitRequest(content="x" * 2000).content == "x" * 2000
    with pytest.raises(ValidationError):
        SubmitRequest(content="")
    with pytest.raises(ValidationError):
        SubmitRequest(content="x" * 2001)

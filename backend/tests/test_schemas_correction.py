import json

import pytest
from pydantic import ValidationError

from app.schemas.correction import LLMResponse, SubmitRequest


def test_llm_response_correction_valid():
    payload = {
        "intent": "correction",
        "correction": {
            "has_errors": True,
            "errors": [{"category": "chinglish", "fragment": "eat", "explanation": "x", "correction": "y"}],
            "rewrite": {"minimal": {"text": "a", "explanation": "e"}, "natural": {"text": "b", "explanation": "f"}},
        },
        "reply": None,
    }
    parsed = LLMResponse.model_validate(payload)
    assert parsed.intent == "correction"
    assert parsed.correction.errors[0].category == "chinglish"


def test_llm_response_follow_up_valid():
    parsed = LLMResponse.model_validate({"intent": "follow_up", "correction": None, "reply": "讲解"})
    assert parsed.reply == "讲解"


def test_llm_response_invalid_category_rejected():
    with pytest.raises(ValidationError):
        LLMResponse.model_validate(
            {"intent": "correction", "correction": {"has_errors": True, "errors": [{"category": "typo", "fragment": "a", "explanation": "b", "correction": "c"}], "rewrite": None}, "reply": None}
        )


def test_submit_request_length_boundaries():
    assert SubmitRequest(content="a").content == "a"
    assert SubmitRequest(content="x" * 2000).content == "x" * 2000
    with pytest.raises(ValidationError):
        SubmitRequest(content="")
    with pytest.raises(ValidationError):
        SubmitRequest(content="x" * 2001)

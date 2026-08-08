import json

import pytest

from app.core.errors import AppError
from app.services.llm_client import MockLLMClient, RealLLMClient, get_llm_client


async def test_mock_llm_returns_responder_output():
    mock = MockLLMClient(responder=lambda msgs: "pong")
    assert await mock.complete([{"role": "user", "content": "hi"}]) == "pong"

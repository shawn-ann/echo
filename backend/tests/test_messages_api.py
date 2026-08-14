import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.llm_client import MockLLMClient, get_llm_client

POST_URL = "/api/v1/messages"
GET_URL = "/api/v1/messages"
LOGIN_URL = "/api/v1/auth/login"


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: mock
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, mock


async def _token(client: AsyncClient) -> str:
    r = await client.post(LOGIN_URL, json={"username": "demo", "password": "demo1234"})
    assert r.status_code == 200
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# T-C-01 提交纠错成功
async def test_post_messages_correction(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["user_message"]["type"] == "correction"
    assert data["assistant_message"]["type"] == "report"
    assert data["assistant_message"]["report"]["has_errors"] is True


# T-C-02 无错误文本
async def test_post_messages_no_error(api):
    client, mock = api
    token = await _token(client)
    mock.responder = lambda msgs: (
        '{"has_errors":false,"errors":[],"rewrite":null,"learnings":[]}'
    )
    r = await client.post(POST_URL, json={"content": "perfect english"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["assistant_message"]["report"]["has_errors"] is False
    assert data["assistant_message"]["report"]["rewrite"] is None


# T-C-03 纯中文也返回纠错报告（单轮纠错，无 follow_up）
async def test_post_messages_chinese_returns_report(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "为什么不能用 very？"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["user_message"]["type"] == "correction"
    assert data["assistant_message"]["type"] == "report"
    assert data["assistant_message"]["report"]["has_errors"] is True


# T-C-04 空内容
async def test_post_messages_empty(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": ""}, headers=_auth(token))
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR"


# T-C-05 超 2000 字符
async def test_post_messages_too_long(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "x" * 2001}, headers=_auth(token))
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR"


# T-C-06 未鉴权
async def test_post_messages_unauthorized(api):
    client, _ = api
    r = await client.post(POST_URL, json={"content": "hello"})
    assert r.status_code == 401


# T-C-07 LLM 未配置 → 503（显式覆盖依赖为抛 503，不依赖环境/.env）
async def test_post_messages_llm_not_configured():
    from app.core.errors import AppError

    app = create_app()

    def _unconfigured():
        raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务未配置，请配置 LLM_BASE_URL/LLM_API_KEY")

    app.dependency_overrides[get_llm_client] = _unconfigured
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _token(c)
        r = await c.post(POST_URL, json={"content": "hello world"}, headers=_auth(token))
        assert r.status_code == 503
        assert r.json()["code"] == "LLM_SERVICE_UNAVAILABLE"


# T-C-08 LLM 返回无效 JSON → 502（重试后）
async def test_post_messages_invalid_llm_response(api):
    client, mock = api
    token = await _token(client)
    mock.responder = lambda msgs: "not-json"
    r = await client.post(POST_URL, json={"content": "hello world"}, headers=_auth(token))
    assert r.status_code == 502
    assert r.json()["code"] == "LLM_RESPONSE_INVALID"
    assert len(mock.calls) == 2  # 首次失败后重试一次


# T-C-09 空历史
async def test_get_messages_empty(api):
    client, _ = api
    token = await _token(client)
    r = await client.get(GET_URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["messages"] == []


# T-C-10 有历史且报告内嵌
async def test_get_messages_with_history(api):
    client, _ = api
    token = await _token(client)
    await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    r = await client.get(GET_URL, headers=_auth(token))
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["type"] for m in msgs] == ["correction", "report"]
    assert msgs[1]["report"]["has_errors"] is True


# T-C-11 数据隔离
async def test_data_isolation(api):
    from sqlalchemy import select as sa_select

    from app.core.security import hash_password
    from app.db import async_session_factory
    from app.models.user import User, UserStatus

    async with async_session_factory() as s:
        s.add(
            User(
                username="alice",
                password_hash=hash_password("alice1234"),
                status=UserStatus.active,
            )
        )
        await s.commit()
    client, _ = api
    token = await _token(client)
    await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    assert len((await client.get(GET_URL, headers=_auth(token))).json()["messages"]) == 2
    r = await client.post(LOGIN_URL, json={"username": "alice", "password": "alice1234"})
    assert r.status_code == 200
    alice_token = r.json()["token"]
    assert (await client.get(GET_URL, headers=_auth(alice_token))).json()["messages"] == []

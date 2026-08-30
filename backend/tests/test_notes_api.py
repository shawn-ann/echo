import json
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import async_session_factory
from app.main import create_app
from app.models.user import User
from app.services.llm_client import MockLLMClient, get_llm_client

POST_URL = "/api/v1/notes/save"
LIST_URL = "/api/v1/notes"
LOGIN_URL = "/api/v1/auth/login"

_ERROR = {"error_type": "主谓不一致", "fragment": "She have", "explanation": "主语 she 第三人称单数", "correction": "She has"}


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient(responder=lambda msgs: json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "description": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "examples": [
                {"text": "She plays tennis.", "note": "play → plays"},
                {"text": "He goes to work.", "note": "go → goes"},
                {"text": "It rains a lot.", "note": "rain → rains"},
            ],
            "references": ["She have"],
        }]
    }, ensure_ascii=False))
    app.dependency_overrides[get_llm_client] = lambda: mock
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client: AsyncClient) -> str:
    r = await client.post(LOGIN_URL, json={"username": "demo", "password": "demo1234"})
    assert r.status_code == 200
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _first_note_id(client, token) -> str:
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    notes = r.json()["notes"]
    assert len(notes) == 1
    return notes[0]["id"]


async def test_save_note_returns_accepted(api):
    client = api
    token = await _token(client)
    r = await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "She have many book",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 202
    assert r.json() == {"accepted": True}


async def test_save_note_unauthorized(api):
    r = await api.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "x", "errors": [_ERROR]})
    assert r.status_code == 401


async def test_save_note_creates_note(api):
    client = api
    token = await _token(client)
    r = await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "She have many book",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 202
    assert r.json() == {"accepted": True}


async def test_list_notes_empty(api):
    client = api
    token = await _token(client)
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["notes"] == []


async def test_list_notes_after_save(api):
    client = api
    token = await _token(client)
    await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    notes = r.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["case_count"] == 1


async def test_get_note_detail_with_examples_and_cases(api):
    client = api
    token = await _token(client)
    await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = await _first_note_id(client, token)
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 200
    detail = r.json()
    assert len(detail["examples"]) == 3
    assert detail["examples"][0]["text"] == "She plays tennis."
    assert len(detail["cases"]) == 1
    assert detail["cases"][0]["fragment"] == "She have"
    assert detail["cases"][0]["correction"] == "She has"


async def test_get_note_detail_not_found(api):
    client = api
    token = await _token(client)
    r = await client.get(f"{LIST_URL}/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_note(api):
    client = api
    token = await _token(client)
    await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = await _first_note_id(client, token)
    r = await client.delete(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r2.status_code == 404


async def test_delete_case(api):
    client = api
    token = await _token(client)
    await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = await _first_note_id(client, token)
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    r = await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(LIST_URL, headers=_auth(token))
    assert r2.json()["notes"] == []


async def test_get_note_detail_other_user_not_found(api):
    """跨用户隔离：用户 B 请求用户 A 的笔记 → 404"""
    from app.core.security import hash_password
    from app.models.user import User, UserStatus

    client = api
    async with async_session_factory() as s:
        s.add(User(username="isol_user", password_hash=hash_password("iso1234"), status=UserStatus.active))
        await s.commit()

    token_a = await _token(client)
    await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "She have many book",
        "errors": [_ERROR],
    }, headers=_auth(token_a))
    note_id = await _first_note_id(client, token_a)

    r_b = await client.post(LOGIN_URL, json={"username": "isol_user", "password": "iso1234"})
    assert r_b.status_code == 200
    token_b = r_b.json()["token"]
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token_b))
    assert r2.status_code == 404


class _RaisingLLMClient:
    async def complete(self, messages):
        raise RuntimeError("llm down")


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_run_save_notes_async_swallows_llm_failure():
    """后台 LLM 失败被 _run_save_notes_async 吞掉，不向上抛"""
    from app.routers.notes import _run_save_notes_async

    uid = await _demo_user_id()
    errors = [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}]
    await _run_save_notes_async(uid, None, "She have many book", errors, _RaisingLLMClient())

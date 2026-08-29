import json

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.llm_client import MockLLMClient, get_llm_client

POST_URL = "/api/v1/notes/save"
LIST_URL = "/api/v1/notes"
LOGIN_URL = "/api/v1/auth/login"

_ERROR = {"error_type": "动词形式", "fragment": "interested in read", "explanation": "介词后加 ing", "correction": "interested in reading"}


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient(responder=lambda msgs: json.dumps({
        "results": [{
            "rule_title": "介词后加 -ing 形式",
            "description": "介词后接动词用动名词形式",
            "example": "interested in read → interested in reading",
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


async def test_save_note_unauthorized(api):
    r = await api.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "x", "errors": [_ERROR]})
    assert r.status_code == 401


async def test_save_note_creates_note(api):
    client = api
    token = await _token(client)
    r = await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "I interested in read",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data["saved_notes"]) == 1
    assert data["saved_notes"][0]["is_new"] is True
    assert data["saved_notes"][0]["rule_title"] == "介词后加 -ing 形式"


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


async def test_get_note_detail(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()["cases"]) == 1


async def test_get_note_detail_not_found(api):
    client = api
    token = await _token(client)
    r = await client.get(f"{LIST_URL}/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_note(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    r = await client.delete(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r2.status_code == 404


async def test_delete_case(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    r = await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(LIST_URL, headers=_auth(token))
    assert r2.json()["notes"] == []

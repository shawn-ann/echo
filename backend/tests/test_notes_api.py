import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db import async_session_factory
from app.main import create_app
from app.models.note import Note, NoteCase
from app.models.user import User, UserStatus
from app.services.llm_client import MockLLMClient, get_llm_client

LIST_URL = "/api/v1/notes"
LOGIN_URL = "/api/v1/auth/login"


def _mock_responder(msgs):
    import json

    return json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "knowledge_point": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "warning": "你常忘给 she/he/it 加 -s",
            "alternatives": ["She runs.", "He goes."],
            "feynman_question": "主语是 she/he/it 时动词怎么变？",
            "error_root": "主谓不一致",
            "cases": [{"change_details": "She go → She goes"}],
        }]
    }, ensure_ascii=False)


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient(responder=_mock_responder)
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


async def _seed_note(client, token, source_text="She go to school.", polished="She goes to school.") -> uuid.UUID:
    """直接入库一条笔记（模拟自动保存结果）"""
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        note = Note(
            user_id=user.id,
            rule_title="第三人称单数主谓一致",
            knowledge_point="一般现在时中，第三人称单数主语动词加 -s/-es",
            warning="w", alternatives=["A"], feynman_question="q",
        )
        s.add(note)
        await s.flush()
        s.add(NoteCase(
            note_id=note.id, user_id=user.id,
            original_sentence=source_text, polished_sentence=polished,
            change_details="She go → She goes", error_root="主谓不一致",
        ))
        await s.commit()
        return note.id


async def test_save_note_route_deleted(api):
    """POST /notes/save 已删除 → 404/405（Starlette 将 /notes/save 命中 /{note_id} 路径 → 405）"""
    client = api
    token = await _token(client)
    r = await client.post("/api/v1/notes/save", json={}, headers=_auth(token))
    assert r.status_code in (404, 405)


async def test_list_notes_empty(api):
    client = api
    token = await _token(client)
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["notes"] == []


async def test_list_notes_after_auto_save(api):
    client = api
    token = await _token(client)
    await _seed_note(client, token)
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    notes = r.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["case_count"] == 1
    assert notes[0]["knowledge_point"] == "一般现在时中，第三人称单数主语动词加 -s/-es"


async def test_get_note_detail_8field(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 200
    detail = r.json()
    assert detail["knowledge_point"] == "一般现在时中，第三人称单数主语动词加 -s/-es"
    assert detail["warning"] == "w"
    assert detail["alternatives"] == ["A"]
    assert detail["feynman_question"] == "q"
    assert len(detail["cases"]) == 1
    case = detail["cases"][0]
    assert case["original_sentence"] == "She go to school."
    assert case["polished_sentence"] == "She goes to school."
    assert case["change_details"] == "She go → She goes"
    assert case["error_root"] == "主谓不一致"


async def test_get_note_detail_not_found(api):
    client = api
    token = await _token(client)
    r = await client.get(f"{LIST_URL}/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_note(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    r = await client.delete(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r2.status_code == 404


async def test_delete_case(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    r = await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(LIST_URL, headers=_auth(token))
    assert r2.json()["notes"] == []


async def test_get_note_detail_other_user_not_found(api):
    client = api
    async with async_session_factory() as s:
        s.add(User(username="isol_user", password_hash=hash_password("iso1234"), status=UserStatus.active))
        await s.commit()
    token_a = await _token(client)
    note_id = await _seed_note(client, token_a)
    r_b = await client.post(LOGIN_URL, json={"username": "isol_user", "password": "iso1234"})
    assert r_b.status_code == 200
    token_b = r_b.json()["token"]
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token_b))
    assert r2.status_code == 404


async def test_delete_case_no_cases_note_gone(api):
    """删空所有案例后笔记不再展示"""
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    # 案例删空后 note 仍存在但详情返回 404（现有语义）
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 404

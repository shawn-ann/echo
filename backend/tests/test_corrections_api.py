from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import async_session_factory
from app.models.correction import Correction
from app.models.user import User


async def _login(client) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"username": "demo", "password": "demo1234"}
    )
    assert r.status_code == 200
    return r.json()["token"]


async def _add_correction() -> None:
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "demo"))
        assert user is not None
        session.add(
            Correction(
                user_id=user.id,
                mode="correction",
                source_text="Yesterday I go to school.",
                report={
                    "schema_version": 1,
                    "errors": [
                        {
                            "severity": "Major",
                            "fragment": "go",
                            "type": "时态错误",
                            "reason": "过去时间用过去式",
                            "fix": "went",
                        }
                    ],
                    "rewrites": [
                        {"id": "minimal", "text": "Yesterday I went to school."}
                    ],
                },
                schema_version=1,
                duration_ms=1200,
                model="test-model",
            )
        )
        await session.commit()


async def test_corrections_requires_auth(client):
    r = await client.get("/api/v1/corrections")
    assert r.status_code == 401


async def test_corrections_returns_user_history(client):
    token = await _login(client)
    await _add_correction()
    r = await client.get(
        "/api/v1/corrections", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()["corrections"]
    assert len(rows) == 1
    assert rows[0]["source_text"] == "Yesterday I go to school."
    assert rows[0]["report"]["rewrites"][0]["id"] == "minimal"
    assert rows[0]["duration_ms"] == 1200


async def test_corrections_paginate_newest_first_with_cursor(client):
    token = await _login(client)
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "demo"))
        assert user is not None
        base = datetime(2026, 11, 28, tzinfo=timezone.utc)
        for index in range(12):
            session.add(
                Correction(
                    user_id=user.id,
                    mode="correction",
                    source_text=f"message-{index}",
                    report={"schema_version": 1, "errors": [], "rewrites": []},
                    schema_version=1,
                    created_at=base + timedelta(seconds=index),
                )
            )
        await session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    first = await client.get("/api/v1/corrections", headers=headers)
    assert first.status_code == 200
    page = first.json()
    assert len(page["corrections"]) == 10
    assert page["has_more"] is True
    assert page["next_cursor"]
    assert [row["source_text"] for row in page["corrections"]] == [
        f"message-{index}" for index in range(11, 1, -1)
    ]

    second = await client.get(
        f"/api/v1/corrections?before={page['next_cursor']}", headers=headers
    )
    assert second.status_code == 200
    page2 = second.json()
    assert len(page2["corrections"]) == 2
    assert page2["has_more"] is False
    assert [row["source_text"] for row in page2["corrections"]] == [
        "message-1",
        "message-0",
    ]

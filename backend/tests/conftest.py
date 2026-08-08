import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://echo:echo@localhost:5432/echo_test"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import hash_password
from app.db import Base, async_session_factory, engine
from app.main import create_app
from app.models.user import User, UserStatus


async def drop_all_tables():
    async with engine.begin() as conn:
        for name in (
            "messages",
            "correction_reports",
            "session_conversations",
            "sessions",
            "users",
        ):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    await drop_all_tables()
    async with engine.begin() as conn:
        await conn.execute(text("DROP TYPE IF EXISTS user_status"))
        await conn.execute(text("DROP TYPE IF EXISTS message_role"))
        await conn.execute(text("DROP TYPE IF EXISTS message_type"))
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        session.add_all(
            [
                User(
                    username="demo",
                    password_hash=hash_password("demo1234"),
                    status=UserStatus.active,
                ),
                User(
                    username="disabled_user",
                    password_hash=hash_password("demo1234"),
                    status=UserStatus.disabled,
                ),
                User(
                    username="deleted_user",
                    password_hash=hash_password("demo1234"),
                    status=UserStatus.deleted,
                ),
            ]
        )
        await session.commit()
    yield
    await drop_all_tables()


@pytest_asyncio.fixture(autouse=True)
async def clean_sessions():
    async with async_session_factory() as session:
        await session.execute(text("TRUNCATE sessions, messages, correction_reports, session_conversations"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

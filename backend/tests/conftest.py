import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://echo:echo@localhost:5432/echo_test"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import hash_password
from app.db import Base, async_session_factory, engine
from app.main import create_app
from app.models.user import User, UserStatus


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS user_status"))
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clean_sessions():
    async with async_session_factory() as session:
        await session.execute(text("TRUNCATE sessions"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

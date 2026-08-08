from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import generate_token, hash_token
from app.db import async_session_factory
from app.main import create_app
from app.models.session import AuthSession
from app.models.user import User

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"


async def _login(client: AsyncClient) -> str:
    r = await client.post(
        LOGIN_URL, json={"username": "demo", "password": "demo1234"}
    )
    assert r.status_code == 200
    return r.json()["token"]


# ---- T-L-01 合法固定账号登录 ----
async def test_login_success(client):
    r = await client.post(
        LOGIN_URL, json={"username": "demo", "password": "demo1234"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["token"]
    assert data["expires_at"]
    assert data["user"]["username"] == "demo"
    assert data["user"]["id"]


# ---- T-L-02 密码错误 ----
async def test_login_wrong_password(client):
    r = await client.post(
        LOGIN_URL, json={"username": "demo", "password": "wrong-password"}
    )
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "AUTH_INVALID_CREDENTIALS"
    assert body["message"] == "用户名或密码错误"


# ---- T-L-03 用户名/密码为空 ----
async def test_login_empty_username(client):
    r = await client.post(LOGIN_URL, json={"username": "", "password": "demo1234"})
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR"


async def test_login_empty_password(client):
    r = await client.post(LOGIN_URL, json={"username": "demo", "password": ""})
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR"


# ---- T-L-04 disabled 账号 ----
async def test_login_disabled_account(client):
    r = await client.post(
        LOGIN_URL, json={"username": "disabled_user", "password": "demo1234"}
    )
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == "AUTH_ACCOUNT_DISABLED"
    assert body["message"] == "账号不可用"


# ---- T-L-05 deleted 账号（按凭证错误处理，不泄露状态）----
async def test_login_deleted_account(client):
    r = await client.post(
        LOGIN_URL, json={"username": "deleted_user", "password": "demo1234"}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_INVALID_CREDENTIALS"


# ---- T-L-06 有效 token 获取当前用户 ----
async def test_me_with_valid_token(client):
    token = await _login(client)
    r = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "demo"
    assert r.json()["id"]


# ---- T-L-07 无/失效 token ----
async def test_me_without_token(client):
    r = await client.get(ME_URL)
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_UNAUTHORIZED"


async def test_me_with_invalid_token(client):
    r = await client.get(ME_URL, headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_UNAUTHORIZED"


async def test_me_with_expired_token(client):
    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "demo"))
        ).scalar_one()
        token = generate_token()
        session.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await session.commit()
    r = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_TOKEN_EXPIRED"


# ---- T-L-08 退出登录后 token 失效 ----
async def test_logout_invalidates_token(client):
    token = await _login(client)
    r = await client.post(LOGOUT_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
    r2 = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 401
    assert r2.json()["code"] == "AUTH_UNAUTHORIZED"


# ---- T-L-09 业务接口无 token → 401 ----
async def test_business_endpoint_requires_auth(client):
    r = await client.get(ME_URL)
    assert r.status_code == 401


# ---- T-L-10 服务重启后旧 token 仍有效（DB 持久化会话）----
async def test_token_survives_restart(client):
    token = await _login(client)
    app2 = create_app()
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as c:
        r = await c.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["username"] == "demo"

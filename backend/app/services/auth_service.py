from datetime import datetime, timedelta, timezone

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import generate_token, hash_token, verify_password
from app.db import get_db
from app.models.session import AuthSession
from app.models.user import User, UserStatus

bearer_scheme = HTTPBearer(auto_error=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at() -> datetime:
    return _utcnow() + timedelta(days=get_settings().SESSION_TTL_DAYS)


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> User | None:
    """校验账号。返回 User 表示成功；返回 None 表示凭证无效（含 deleted 账号）。"""
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None or user.status == UserStatus.deleted:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status == UserStatus.disabled:
        raise AppError(403, "AUTH_ACCOUNT_DISABLED", "账号不可用")
    return user


async def create_session(session: AsyncSession, user: User) -> tuple[str, datetime]:
    token = generate_token()
    expires_at = _expires_at()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=expires_at,
            created_at=_utcnow(),
            last_used_at=_utcnow(),
        )
    )
    await session.commit()
    return token, expires_at


async def resolve_session(
    session: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthSession:
    """校验 token 并返回对应会话；失败抛 401；成功后滑动续期。"""
    if credentials is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "未登录或令牌失效")
    token_hash = hash_token(credentials.credentials)
    auth_session = (
        await session.execute(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if auth_session is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "未登录或令牌失效")
    if auth_session.expires_at < _utcnow():
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "会话已过期，请重新登录")
    auth_session.expires_at = _expires_at()
    auth_session.last_used_at = _utcnow()
    await session.commit()
    return auth_session


async def get_current_session(
    session: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthSession:
    return await resolve_session(session, credentials)


async def get_current_user(
    auth_session: AuthSession = Depends(get_current_session),
    session: AsyncSession = Depends(get_db),
) -> User:
    user = await session.get(User, auth_session.user_id)
    if user is None or user.status != UserStatus.active:
        raise AppError(401, "AUTH_UNAUTHORIZED", "未登录或令牌失效")
    return user

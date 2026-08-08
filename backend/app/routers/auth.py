from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import get_db
from app.models.session import AuthSession
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import (
    authenticate_user,
    create_session,
    get_current_session,
    get_current_user,
)
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    user = await authenticate_user(session, payload.username, payload.password)
    if user is None:
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "用户名或密码错误")
    token, expires_at = await create_session(session, user)
    return TokenResponse(
        token=token, expires_at=expires_at, user=UserOut.model_validate(user)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    auth_session: AuthSession = Depends(get_current_session),
    session: AsyncSession = Depends(get_db),
):
    await session.delete(auth_session)
    await session.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user

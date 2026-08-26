from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserStatus


async def seed_default_user(session: AsyncSession) -> None:
    """幂等创建 MVP 固定种子账号（shawn/shawn!QAZ1qaz，active）。"""
    settings = get_settings()
    existing = await session.execute(
        select(User).where(User.username == settings.SEED_USERNAME)
    )
    if existing.scalar_one_or_none() is not None:
        return
    session.add(
        User(
            username=settings.SEED_USERNAME,
            password_hash=hash_password(settings.SEED_PASSWORD),
            status=UserStatus.active,
        )
    )
    await session.commit()

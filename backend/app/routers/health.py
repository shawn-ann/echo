from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "degraded", "db": "unavailable"}
        )
    return {"status": "ok", "db": "connected"}

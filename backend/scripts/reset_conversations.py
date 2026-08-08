"""清空开发库纠错相关表（供 E2E globalSetup 调用，保证套件封闭）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import async_session_factory


async def main() -> None:
    async with async_session_factory() as s:
        await s.execute(text("TRUNCATE messages, correction_reports, session_conversations"))
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())

"""清空开发库纠错相关表（供 E2E globalSetup 调用，保证套件封闭）。"""
import asyncio
import sys
from pathlib import Path

# 以 `python scripts/reset_conversations.py` 从 backend 根运行时，sys.path[0] 是
# scripts/ 目录而非 backend 根，app 包不在路径上，需手动加入 backend 根。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import async_session_factory


async def main() -> None:
    async with async_session_factory() as s:
        await s.execute(
            text("TRUNCATE messages, correction_reports, session_conversations, notes, note_cases")
        )
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())

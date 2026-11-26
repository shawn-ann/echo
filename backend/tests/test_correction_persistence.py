import json
import uuid

from sqlalchemy import select

from app.db import async_session_factory
from app.models.correction import Correction
from app.models.user import User
from app.schemas.coach import CoachCorrection
from app.services.correction_stream import save_correction, storage_report


def _correction() -> CoachCorrection:
    return CoachCorrection.model_validate(
        {
            "errors": [
                {
                    "severity": "Major",
                    "fragment": "go",
                    "type": "时态错误",
                    "reason": "过去时间用过去式",
                    "fix": "went",
                }
            ],
            "rewrites": {
                "formal": {"text": "Formal.", "note": "正式"},
                "casual": {"text": "Casual.", "note": "口语"},
                "minimal": {"text": "Minimal."},
            },
        }
    )


def test_storage_report_uses_rewrite_array():
    report = storage_report(_correction())
    assert report["schema_version"] == 1
    assert [item["id"] for item in report["rewrites"]] == [
        "formal",
        "casual",
        "minimal",
    ]
    assert report["rewrites"][0]["note"] == "正式"
    assert "note" not in report["rewrites"][2]


async def test_save_correction_persists_report():
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "demo"))
        assert user is not None
        user_id = user.id

    correction_id = await save_correction(
        user_id, "correction", "Yesterday I go.", _correction(), 1234
    )
    assert correction_id is not None

    async with async_session_factory() as session:
        record = await session.get(Correction, uuid.UUID(correction_id))
        assert record is not None
        assert record.user_id == user_id
        assert record.source_text == "Yesterday I go."
        assert record.mode == "correction"
        assert record.duration_ms == 1234
        assert record.report["errors"][0]["fix"] == "went"
        assert isinstance(record.report["rewrites"], list)
        assert json.dumps(record.report)

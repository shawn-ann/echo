import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_notes_user_id", ondelete="CASCADE"), nullable=False
    )
    rule_title: Mapped[str] = mapped_column(String(200), nullable=False)
    knowledge_point: Mapped[str] = mapped_column(Text, nullable=False)
    warning: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    feynman_question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NoteCase(Base):
    __tablename__ = "note_cases"
    __table_args__ = (
        UniqueConstraint(
            "note_id", "user_id", "original_sentence",
            name="uq_note_cases_dedup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notes.id", name="fk_note_cases_note_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_note_cases_user_id", ondelete="CASCADE"), nullable=False
    )
    original_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    polished_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    change_details: Mapped[str] = mapped_column(Text, nullable=False)
    error_root: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", name="fk_note_cases_message_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from lectio.db.base import Base


class Bookmark(Base):
    """A moment of a lecture a user saved, optionally with a note."""

    __tablename__ = "bookmarks"
    __table_args__ = (
        CheckConstraint(
            "position_seconds >= 0",
            name="ck_bookmarks_position",
        ),
        CheckConstraint(
            "char_length(note) <= 2000",
            name="ck_bookmarks_note_length",
        ),
        Index(
            "ix_bookmarks_user_lecture_position",
            "user_id",
            "lecture_id",
            "position_seconds",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
    )

    lecture_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "lectures.id",
            ondelete="CASCADE",
        ),
    )

    position_seconds: Mapped[float] = mapped_column(
        Float,
    )

    note: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

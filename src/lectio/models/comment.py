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


class Comment(Base):
    """A message in a lecture's discussion, optionally about one moment."""

    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(
            "char_length(text) BETWEEN 1 AND 2000",
            name="ck_comments_text_length",
        ),
        CheckConstraint(
            "position_seconds >= 0",
            name="ck_comments_position",
        ),
        Index(
            "ix_comments_lecture_created_at",
            "lecture_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    lecture_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "lectures.id",
            ondelete="CASCADE",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
    )

    text: Mapped[str] = mapped_column(
        Text,
    )

    position_seconds: Mapped[float | None] = mapped_column(
        Float,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

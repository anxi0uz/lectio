from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lectio.db.base import Base


class QuizAttempt(Base):
    """A user's latest answers to a lecture's quiz.

    Only the latest attempt is kept; a regenerated quiz drops them all, since
    the answers no longer match its questions.
    """

    __tablename__ = "quiz_attempts"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    lecture_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "lectures.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        index=True,
    )

    # Chosen option index per question.
    answers: Mapped[list[int]] = mapped_column(
        JSONB,
    )

    correct: Mapped[int] = mapped_column(
        Integer,
    )

    total: Mapped[int] = mapped_column(
        Integer,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

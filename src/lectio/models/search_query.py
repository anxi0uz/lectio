from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from lectio.db.base import Base


class SearchQuery(Base):
    """A search made by a signed-in user, for the history in their account."""

    __tablename__ = "search_queries"
    __table_args__ = (
        Index(
            "ix_search_queries_user_created_at",
            "user_id",
            "created_at",
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

    query: Mapped[str] = mapped_column(
        String(500),
    )

    lecture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "lectures.id",
            ondelete="SET NULL",
        ),
    )

    course_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "courses.id",
            ondelete="SET NULL",
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

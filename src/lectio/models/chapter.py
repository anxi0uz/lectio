from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lectio.db.base import Base

if TYPE_CHECKING:
    from lectio.models.lecture import Lecture


class Chapter(Base):
    """Table-of-contents entry: level 1 is a section, level 2 a subsection."""

    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint(
            "level IN (1, 2)",
            name="ck_chapters_level",
        ),
        Index(
            "ix_chapters_lecture_position",
            "lecture_id",
            "position",
            unique=True,
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

    position: Mapped[int] = mapped_column(
        Integer,
    )

    level: Mapped[int] = mapped_column(
        Integer,
    )

    title: Mapped[str] = mapped_column(
        String(300),
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
    )

    start_seconds: Mapped[float] = mapped_column(
        Float,
    )

    lecture: Mapped["Lecture"] = relationship(
        back_populates="chapters",
        lazy="raise",
    )

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lectio.db.base import Base

if TYPE_CHECKING:
    from lectio.models.lecture import Lecture


class Segment(Base):
    """One recognized phrase; the unit of subtitles."""

    __tablename__ = "segments"
    __table_args__ = (
        Index(
            "ix_segments_lecture_position",
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

    start_seconds: Mapped[float] = mapped_column(
        Float,
    )

    end_seconds: Mapped[float] = mapped_column(
        Float,
    )

    text: Mapped[str] = mapped_column(
        Text,
    )

    lecture: Mapped["Lecture"] = relationship(
        back_populates="segments",
        lazy="raise",
    )

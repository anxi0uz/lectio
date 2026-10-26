from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lectio.db.base import Base
from lectio.models.enums import LectureStatus, SourceType

if TYPE_CHECKING:
    from lectio.models.chapter import Chapter
    from lectio.models.chunk import Chunk
    from lectio.models.course import Course
    from lectio.models.segment import Segment


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (
        CheckConstraint(
            "progress BETWEEN 0 AND 1",
            name="ck_lectures_progress_range",
        ),
        Index(
            "ix_lectures_course_created_at",
            "course_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    course_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "courses.id",
            ondelete="SET NULL",
        ),
    )

    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(300),
    )

    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            native_enum=False,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        ),
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
    )

    video_path: Mapped[str | None] = mapped_column(
        Text,
    )

    video_mime_type: Mapped[str | None] = mapped_column(
        String(100),
    )

    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
    )

    language: Mapped[str | None] = mapped_column(
        String(16),
    )

    status: Mapped[LectureStatus] = mapped_column(
        Enum(
            LectureStatus,
            native_enum=False,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=LectureStatus.PENDING,
        index=True,
    )

    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
    )

    summary_error: Mapped[str | None] = mapped_column(
        Text,
    )

    key_terms: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
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

    course: Mapped["Course | None"] = relationship(
        back_populates="lectures",
        lazy="raise",
    )

    segments: Mapped[list["Segment"]] = relationship(
        back_populates="lecture",
        lazy="raise",
        passive_deletes=True,
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="lecture",
        lazy="raise",
        passive_deletes=True,
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="lecture",
        lazy="raise",
        passive_deletes=True,
    )

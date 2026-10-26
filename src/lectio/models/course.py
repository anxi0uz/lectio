from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lectio.db.base import Base

if TYPE_CHECKING:
    from lectio.models.lecture import Lecture


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(300),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    lectures: Mapped[list["Lecture"]] = relationship(
        back_populates="course",
        lazy="raise",
    )

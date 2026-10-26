from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Note = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=2000,
    ),
]


class BookmarkCreate(BaseModel):
    position_seconds: float = Field(ge=0)
    note: Note | None = None


class BookmarkUpdate(BaseModel):
    position_seconds: float | None = Field(default=None, ge=0)
    note: Note | None = None


class BookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lecture_id: UUID
    position_seconds: float
    note: str | None
    created_at: datetime
    updated_at: datetime


class BookmarkWithLectureResponse(BookmarkResponse):
    lecture_title: str

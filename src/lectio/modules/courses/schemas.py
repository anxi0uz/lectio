from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

CourseTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=300,
    ),
]


class CourseCreate(BaseModel):
    title: CourseTitle
    description: str | None = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID | None
    title: str
    description: str | None
    created_at: datetime
    lectures_count: int = 0
    total_duration_seconds: float = 0.0

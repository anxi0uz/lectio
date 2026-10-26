from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from lectio.modules.lectures.schemas import LectureResponse


class ProgressUpdate(BaseModel):
    position_seconds: float = Field(ge=0)
    # Omitted: decided by position (90% of the lecture counts as watched).
    completed: bool | None = None


class ProgressResponse(BaseModel):
    lecture_id: UUID
    position_seconds: float
    completed: bool
    updated_at: datetime | None


class ContinueWatchingItem(BaseModel):
    lecture: LectureResponse
    position_seconds: float
    updated_at: datetime

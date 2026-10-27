from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
)

from lectio.models.enums import SEARCHABLE_STATUSES, LectureStatus, SourceType

LectureTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=300,
    ),
]


class LectureImport(BaseModel):
    url: AnyHttpUrl
    title: LectureTitle | None = None
    course_id: UUID | None = None


class LectureUpdate(BaseModel):
    title: LectureTitle | None = None
    course_id: UUID | None = None


class LectureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID | None
    owner_id: UUID | None
    title: str
    source_type: SourceType
    source_url: str | None
    duration_seconds: float | None
    language: str | None
    status: LectureStatus
    progress: float
    error: str | None
    created_at: datetime
    updated_at: datetime

    # Storage paths are internal; clients get video_url instead.
    video_path: str | None = Field(
        default=None,
        exclude=True,
    )

    @computed_field
    @property
    def video_url(self) -> str | None:
        if self.video_path is None:
            return None

        return f"/api/v1/lectures/{self.id}/video"

    video_mime_type: str | None = Field(
        default=None,
        exclude=True,
    )

    @computed_field
    @property
    def thumbnail_url(self) -> str | None:
        is_video = (self.video_mime_type or "video/").startswith("video/")

        if self.video_path is None or not is_video:
            return None

        # The version changes whenever the lecture row does, so browsers can
        # cache each URL forever.
        version = int(self.updated_at.timestamp())

        return f"/api/v1/lectures/{self.id}/thumbnail?v={version}"

    @computed_field
    @property
    def subtitles_url(self) -> str | None:
        if self.status not in SEARCHABLE_STATUSES:
            return None

        return f"/api/v1/lectures/{self.id}/subtitles.vtt"

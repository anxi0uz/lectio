from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from lectio.modules.users.schemas import PublicUserResponse

CommentText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
    ),
]


class CommentCreate(BaseModel):
    text: CommentText
    # The moment of the video the comment is about, if any.
    position_seconds: float | None = Field(default=None, ge=0)


class CommentResponse(BaseModel):
    id: UUID
    lecture_id: UUID
    author: PublicUserResponse
    text: str
    position_seconds: float | None
    created_at: datetime

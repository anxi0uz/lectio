from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from lectio.modules.search.schemas import SearchHit

Question = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
    ),
]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(max_length=8000)]


class QuestionRequest(BaseModel):
    question: Question
    lecture_id: UUID | None = None
    course_id: UUID | None = None
    # Previous turns of the conversation, oldest first.
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
    )


class AnswerResponse(BaseModel):
    # Markdown; [n] refers to sources[n - 1].
    answer: str
    sources: list[SearchHit]

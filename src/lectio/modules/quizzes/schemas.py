from uuid import UUID

from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    # Index into options.
    answer: int
    explanation: str
    # Where the lecture explains the answer.
    start_seconds: float | None = None


class QuizResponse(BaseModel):
    lecture_id: UUID
    # Empty until generated.
    questions: list[QuizQuestion]


class DraftQuestion(BaseModel):
    """One question as the model returns it."""

    question: str = Field(min_length=1)
    correct: str = Field(min_length=1)
    wrong: list[str] = Field(min_length=2)
    explanation: str = ""
    start: float | None = None

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lectio.modules.users.schemas import PublicUserResponse


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


class QuizAttemptCreate(BaseModel):
    # Chosen option index per question, in order.
    answers: list[int] = Field(max_length=50)


class QuizAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answers: list[int]
    correct: int
    total: int
    updated_at: datetime


class QuestionStats(BaseModel):
    question: str
    options: list[str]
    answer: int
    # How many students chose each option.
    option_counts: list[int]
    correct_share: float


class StudentResult(BaseModel):
    user: PublicUserResponse
    correct: int
    total: int
    updated_at: datetime


class QuizStatsResponse(BaseModel):
    attempts: int
    # Share of right answers over all attempts; None without attempts.
    average_share: float | None
    questions: list[QuestionStats]
    students: list[StudentResult]

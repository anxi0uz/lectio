from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.config import get_settings
from lectio.ml.llm import LLMClient
from lectio.models import Chunk
from lectio.models.enums import LectureStatus
from lectio.modules.lectures.service import get_lecture_by_id
from lectio.modules.quizzes.exceptions import QuizNotReadyError
from lectio.modules.quizzes.generator import generate_quiz
from lectio.modules.quizzes.schemas import QuizQuestion, QuizResponse

log = structlog.get_logger(
    component="quizzes.service",
)


async def get_quiz(
    db: AsyncSession,
    lecture_id: UUID,
) -> QuizResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    return QuizResponse(
        lecture_id=lecture.id,
        questions=[QuizQuestion.model_validate(item) for item in lecture.quiz],
    )


async def create_quiz(
    db: AsyncSession,
    llm: LLMClient,
    lecture_id: UUID,
) -> QuizResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    if lecture.status != LectureStatus.READY:
        raise QuizNotReadyError

    chunks = await db.scalars(
        select(Chunk)
        .where(Chunk.lecture_id == lecture_id)
        .order_by(Chunk.position.asc())
    )

    questions = await generate_quiz(
        llm,
        lecture.title,
        chunks.all(),
        get_settings().llm_part_chars,
    )

    lecture.quiz = [question.model_dump() for question in questions]
    await db.flush()

    log.info(
        "quiz_generated",
        lecture_id=str(lecture_id),
        questions=len(questions),
    )

    return QuizResponse(
        lecture_id=lecture.id,
        questions=questions,
    )

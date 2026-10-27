from uuid import UUID

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.config import get_settings
from lectio.ml.llm import LLMClient
from lectio.models import Chunk, Lecture, QuizAttempt, User
from lectio.models.enums import LectureStatus
from lectio.modules.lectures.service import get_lecture_by_id, get_managed_lecture
from lectio.modules.quizzes.exceptions import (
    QuizAnswersMismatchError,
    QuizMissingError,
    QuizNotReadyError,
)
from lectio.modules.quizzes.generator import generate_quiz
from lectio.modules.quizzes.schemas import (
    QuestionStats,
    QuizAttemptCreate,
    QuizAttemptResponse,
    QuizQuestion,
    QuizResponse,
    QuizStatsResponse,
    StudentResult,
)
from lectio.modules.users.schemas import PublicUserResponse

log = structlog.get_logger(
    component="quizzes.service",
)


def _questions(lecture: Lecture) -> list[QuizQuestion]:
    return [QuizQuestion.model_validate(item) for item in lecture.quiz]


async def get_quiz(
    db: AsyncSession,
    lecture_id: UUID,
) -> QuizResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    return QuizResponse(
        lecture_id=lecture.id,
        questions=_questions(lecture),
    )


async def create_quiz(
    db: AsyncSession,
    llm: LLMClient,
    lecture_id: UUID,
    user: User,
) -> QuizResponse:
    lecture = await get_managed_lecture(db, lecture_id, user)

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

    # Old answers refer to questions that no longer exist.
    await db.execute(
        delete(QuizAttempt).where(QuizAttempt.lecture_id == lecture_id),
    )
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


async def get_attempt(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> QuizAttempt | None:
    return await db.get(QuizAttempt, (user_id, lecture_id))


async def save_attempt(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
    data: QuizAttemptCreate,
) -> QuizAttempt:
    lecture = await get_lecture_by_id(db, lecture_id)
    questions = _questions(lecture)

    if not questions:
        raise QuizMissingError

    if len(data.answers) != len(questions) or any(
        not 0 <= answer < len(question.options)
        for answer, question in zip(data.answers, questions, strict=True)
    ):
        raise QuizAnswersMismatchError

    correct = sum(
        answer == question.answer
        for answer, question in zip(data.answers, questions, strict=True)
    )
    values = {
        "answers": data.answers,
        "correct": correct,
        "total": len(questions),
    }

    attempt = await db.scalar(
        insert(QuizAttempt)
        .values(user_id=user_id, lecture_id=lecture_id, **values)
        .on_conflict_do_update(
            index_elements=[QuizAttempt.user_id, QuizAttempt.lecture_id],
            set_={**values, "updated_at": func.now()},
        )
        .returning(QuizAttempt),
        # An attempt loaded earlier in the session would hide the new values.
        execution_options={"populate_existing": True},
    )

    if attempt is None:
        raise QuizMissingError

    log.info(
        "quiz_attempt_saved",
        lecture_id=str(lecture_id),
        correct=correct,
        total=len(questions),
    )

    return attempt


async def get_quiz_stats(
    db: AsyncSession,
    lecture_id: UUID,
    user: User,
) -> QuizStatsResponse:
    lecture = await get_managed_lecture(db, lecture_id, user)
    questions = _questions(lecture)

    rows = await db.execute(
        select(QuizAttempt, User)
        .join(User, User.id == QuizAttempt.user_id)
        .where(QuizAttempt.lecture_id == lecture_id)
        .order_by(QuizAttempt.updated_at.desc())
    )
    attempts = list(rows.all())

    question_stats: list[QuestionStats] = []

    for index, question in enumerate(questions):
        counts = [0] * len(question.options)

        for attempt, _ in attempts:
            if index < len(attempt.answers):
                counts[attempt.answers[index]] += 1

        question_stats.append(
            QuestionStats(
                question=question.question,
                options=question.options,
                answer=question.answer,
                option_counts=counts,
                correct_share=counts[question.answer] / len(attempts)
                if attempts
                else 0.0,
            )
        )

    answered = sum(attempt.total for attempt, _ in attempts)

    return QuizStatsResponse(
        attempts=len(attempts),
        average_share=(
            sum(attempt.correct for attempt, _ in attempts) / answered
            if answered
            else None
        ),
        questions=question_stats,
        students=[
            StudentResult(
                user=PublicUserResponse.model_validate(student),
                correct=attempt.correct,
                total=attempt.total,
                updated_at=attempt.updated_at,
            )
            for attempt, student in attempts
        ],
    )


def to_attempt_response(
    attempt: QuizAttempt | None,
) -> QuizAttemptResponse | None:
    if attempt is None:
        return None

    return QuizAttemptResponse.model_validate(attempt)

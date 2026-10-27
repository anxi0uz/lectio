from uuid import UUID

from fastapi import APIRouter

from lectio.api.dependencies import LLMDep, SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.quizzes.schemas import (
    QuizAttemptCreate,
    QuizAttemptResponse,
    QuizResponse,
    QuizStatsResponse,
)
from lectio.modules.quizzes.service import (
    create_quiz,
    get_quiz,
    get_quiz_stats,
    save_attempt,
)

router = APIRouter(
    prefix="/lectures/{lecture_id}/quiz",
    tags=["Quizzes"],
)


@router.get(
    "",
    response_model=QuizResponse,
)
async def get_quiz_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> QuizResponse:
    """The lecture's quiz; no questions until its teacher generates one."""
    return await get_quiz(db, lecture_id)


@router.post(
    "",
    response_model=QuizResponse,
)
async def create_quiz_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    llm: LLMDep,
) -> QuizResponse:
    """Generate a new quiz with the language model; takes up to a minute.

    Only for those who manage the lecture. Replaces the previous quiz and
    drops its attempts.
    """
    return await create_quiz(db, llm, lecture_id, current_user)


@router.put(
    "/attempt",
    response_model=QuizAttemptResponse,
)
async def save_attempt_endpoint(
    lecture_id: UUID,
    payload: QuizAttemptCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> QuizAttemptResponse:
    """Submit answers to every question; replaces the user's previous attempt."""
    attempt = await save_attempt(db, current_user.id, lecture_id, payload)

    return QuizAttemptResponse.model_validate(attempt)


@router.get(
    "/stats",
    response_model=QuizStatsResponse,
)
async def get_quiz_stats_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> QuizStatsResponse:
    """How students answered; only for those who manage the lecture."""
    return await get_quiz_stats(db, lecture_id, current_user)

from uuid import UUID

from fastapi import APIRouter, Depends

from lectio.api.dependencies import LLMDep, SessionDep
from lectio.modules.auth.dependencies import get_current_user
from lectio.modules.quizzes.schemas import QuizResponse
from lectio.modules.quizzes.service import create_quiz, get_quiz

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
    """The last generated quiz; no questions until someone generates one."""
    return await get_quiz(db, lecture_id)


@router.post(
    "",
    response_model=QuizResponse,
    # Only signed-in users may spend the model's time.
    dependencies=[Depends(get_current_user)],
)
async def create_quiz_endpoint(
    lecture_id: UUID,
    db: SessionDep,
    llm: LLMDep,
) -> QuizResponse:
    """Generate a new quiz with the language model; takes up to a minute.

    Replaces the previous quiz of the lecture for everyone.
    """
    return await create_quiz(db, llm, lecture_id)

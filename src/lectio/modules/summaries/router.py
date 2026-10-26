from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, status

from lectio.api.dependencies import RedisDep, SessionDep
from lectio.core.jobs import JobKind, enqueue_job
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.summaries.schemas import SummaryResponse
from lectio.modules.summaries.service import (
    ensure_can_resummarize,
    get_summary,
)

router = APIRouter(
    prefix="/lectures/{lecture_id}/summary",
    tags=["Summaries"],
)


@router.get(
    "",
    response_model=SummaryResponse,
)
async def get_summary_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> SummaryResponse:
    """Summary, table of contents and key terms; empty until generated."""
    return await get_summary(db, lecture_id)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_summary_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
) -> None:
    await ensure_can_resummarize(db, lecture_id, current_user)

    background_tasks.add_task(
        enqueue_job,
        redis,
        JobKind.SUMMARIZE,
        lecture_id,
    )

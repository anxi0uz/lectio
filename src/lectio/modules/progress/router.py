from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.progress.schemas import (
    ContinueWatchingItem,
    ProgressResponse,
    ProgressUpdate,
)
from lectio.modules.progress.service import (
    get_progress,
    list_continue_watching,
    save_progress,
)

router = APIRouter(
    tags=["Progress"],
)


@router.get(
    "/lectures/{lecture_id}/progress",
    response_model=ProgressResponse,
)
async def get_progress_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> ProgressResponse:
    """Where to resume; zero for a lecture never opened."""
    return await get_progress(db, current_user.id, lecture_id)


@router.put(
    "/lectures/{lecture_id}/progress",
    response_model=ProgressResponse,
)
async def save_progress_endpoint(
    lecture_id: UUID,
    payload: ProgressUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> ProgressResponse:
    """Call it every few seconds while playing and on pause."""
    return await save_progress(
        db,
        current_user.id,
        lecture_id,
        payload,
    )


@router.get(
    "/me/continue-watching",
    response_model=list[ContinueWatchingItem],
)
async def continue_watching_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[ContinueWatchingItem]:
    return await list_continue_watching(db, current_user.id, limit)

from uuid import UUID

from fastapi import APIRouter

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.dashboard.schemas import (
    DashboardResponse,
    LectureStateResponse,
    LectureStatsResponse,
)
from lectio.modules.dashboard.service import (
    get_dashboard,
    get_lecture_state,
    get_lecture_stats,
)

router = APIRouter(
    tags=["Dashboard"],
)


@router.get(
    "/me/dashboard",
    response_model=DashboardResponse,
)
async def dashboard_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> DashboardResponse:
    return await get_dashboard(db, current_user)


@router.get(
    "/lectures/{lecture_id}/me",
    response_model=LectureStateResponse,
)
async def lecture_state_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> LectureStateResponse:
    """One request for the lecture page: resume position, favorite flag,
    enrollment, bookmarks and whether the user may edit the lecture."""
    return await get_lecture_state(db, current_user, lecture_id)


@router.get(
    "/lectures/{lecture_id}/stats",
    response_model=LectureStatsResponse,
)
async def lecture_stats_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> LectureStatsResponse:
    """Views, completion, likes, discussion and quiz results in aggregate."""
    return await get_lecture_stats(db, lecture_id)

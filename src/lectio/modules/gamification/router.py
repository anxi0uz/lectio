from fastapi import APIRouter

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.gamification.schemas import (
    LeaderboardResponse,
    MyAchievementsResponse,
)
from lectio.modules.gamification.service import get_leaderboard, get_my_achievements

router = APIRouter(
    tags=["Gamification"],
)


@router.get(
    "/me/achievements",
    response_model=MyAchievementsResponse,
)
async def my_achievements_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> MyAchievementsResponse:
    """XP, level and every achievement with progress toward it."""
    return await get_my_achievements(db, current_user.id)


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
)
async def leaderboard_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> LeaderboardResponse:
    """Top students by XP; only for signed-in users, since it shows names."""
    return await get_leaderboard(db, current_user.id)

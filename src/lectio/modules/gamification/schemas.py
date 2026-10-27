from pydantic import BaseModel

from lectio.modules.users.schemas import PublicUserResponse


class AchievementResponse(BaseModel):
    id: str
    title: str
    description: str
    progress: int
    target: int
    unlocked: bool


class LevelResponse(BaseModel):
    xp: int
    level: int
    # XP at which the current level started and the next one begins.
    level_xp: int
    next_level_xp: int


class MyAchievementsResponse(BaseModel):
    level: LevelResponse
    achievements: list[AchievementResponse]


class LeaderboardEntry(BaseModel):
    rank: int
    user: PublicUserResponse
    level: LevelResponse
    achievements: int


class LeaderboardResponse(BaseModel):
    top: list[LeaderboardEntry]
    # The requesting user's place, also when outside the top.
    me: LeaderboardEntry | None

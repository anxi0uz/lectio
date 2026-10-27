from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import (
    Bookmark,
    Comment,
    Enrollment,
    LectureLike,
    QuizAttempt,
    SearchQuery,
    User,
    WatchProgress,
)
from lectio.models.enums import UserRole
from lectio.modules.gamification.schemas import (
    AchievementResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    LevelResponse,
    MyAchievementsResponse,
)
from lectio.modules.users.schemas import PublicUserResponse

LEADERBOARD_SIZE = 10
# Searching is cheap; past this it stops counting toward XP.
SEARCH_XP_CAP = 50


@dataclass(slots=True)
class Activity:
    """Counts of what a user did, read from the tables that already exist:
    nothing is stored for the game itself."""

    started: int = 0
    completed: int = 0
    quizzes: int = 0
    perfect_quizzes: int = 0
    correct_answers: int = 0
    comments: int = 0
    bookmarks: int = 0
    searches: int = 0
    likes: int = 0
    enrollments: int = 0

    @property
    def xp(self) -> int:
        return (
            self.started * 5
            + self.completed * 50
            + self.correct_answers * 10
            + self.perfect_quizzes * 20
            + self.comments * 5
            + self.bookmarks * 2
            + min(self.searches, SEARCH_XP_CAP)
            + self.enrollments * 10
        )


@dataclass(frozen=True, slots=True)
class Achievement:
    id: str
    title: str
    description: str
    metric: str
    target: int


ACHIEVEMENTS = (
    Achievement("first_step", "Первый шаг", "Начать смотреть лекцию", "started", 1),
    Achievement("finisher", "До последней минуты", "Досмотреть лекцию", "completed", 1),
    Achievement("marathon", "Марафонец", "Досмотреть 5 лекций", "completed", 5),
    Achievement("quiz_first", "Проверил себя", "Пройти тест по лекции", "quizzes", 1),
    Achievement(
        "quiz_perfect",
        "Отличник",
        "Пройти тест без единой ошибки",
        "perfect_quizzes",
        1,
    ),
    Achievement("quiz_master", "Знаток", "Пройти 5 тестов", "quizzes", 5),
    Achievement(
        "curious", "Любопытный", "Задать 10 поисковых запросов", "searches", 10
    ),
    Achievement("notes", "Конспектирую", "Поставить 5 закладок", "bookmarks", 5),
    Achievement("voice", "Голос аудитории", "Оставить 3 комментария", "comments", 3),
    Achievement("enrolled", "Зачислен", "Записаться на курс", "enrollments", 1),
    Achievement("fan", "Ценитель", "Поставить 5 лайков", "likes", 5),
)


def level_threshold(level: int) -> int:
    """XP needed to reach a level: 0, 100, 300, 600, 1000…"""
    return 50 * level * (level - 1)


def to_level(xp: int) -> LevelResponse:
    level = 1

    while level_threshold(level + 1) <= xp:
        level += 1

    return LevelResponse(
        xp=xp,
        level=level,
        level_xp=level_threshold(level),
        next_level_xp=level_threshold(level + 1),
    )


def to_achievements(activity: Activity) -> list[AchievementResponse]:
    return [
        AchievementResponse(
            id=achievement.id,
            title=achievement.title,
            description=achievement.description,
            progress=min(getattr(activity, achievement.metric), achievement.target),
            target=achievement.target,
            unlocked=getattr(activity, achievement.metric) >= achievement.target,
        )
        for achievement in ACHIEVEMENTS
    ]


def _per_user(column: Any, *aggregates: Any) -> Select[*tuple[Any, ...]]:
    return select(column, *aggregates).group_by(column)


async def collect_activity(
    db: AsyncSession,
    user_id: UUID | None = None,
) -> dict[UUID, Activity]:
    """Activity of one user, or of everyone who did anything."""
    queries: list[tuple[tuple[str, ...], Select[*tuple[Any, ...]]]] = [
        (
            ("started", "completed"),
            _per_user(
                WatchProgress.user_id,
                func.count(),
                func.count(WatchProgress.completed_at),
            ),
        ),
        (
            ("quizzes", "perfect_quizzes", "correct_answers"),
            _per_user(
                QuizAttempt.user_id,
                func.count(),
                func.count().filter(QuizAttempt.correct == QuizAttempt.total),
                func.sum(QuizAttempt.correct),
            ),
        ),
        (("comments",), _per_user(Comment.user_id, func.count())),
        (("bookmarks",), _per_user(Bookmark.user_id, func.count())),
        (("searches",), _per_user(SearchQuery.user_id, func.count())),
        (("likes",), _per_user(LectureLike.user_id, func.count())),
        (("enrollments",), _per_user(Enrollment.user_id, func.count())),
    ]

    activity: defaultdict[UUID, Activity] = defaultdict(Activity)

    for fields, query in queries:
        if user_id is not None:
            # The first selected column is the table's user_id.
            query = query.where(query.selected_columns[0] == user_id)

        for row in await db.execute(query):
            for field, value in zip(fields, row[1:], strict=True):
                setattr(activity[row[0]], field, int(value or 0))

    return dict(activity)


async def get_my_achievements(
    db: AsyncSession,
    user_id: UUID,
) -> MyAchievementsResponse:
    activity = (await collect_activity(db, user_id)).get(user_id, Activity())

    return MyAchievementsResponse(
        level=to_level(activity.xp),
        achievements=to_achievements(activity),
    )


async def get_leaderboard(
    db: AsyncSession,
    user_id: UUID,
) -> LeaderboardResponse:
    activity = await collect_activity(db)
    users = {
        user.id: user
        for user in (
            await db.scalars(
                select(User).where(
                    User.id.in_(activity.keys()),
                    User.is_active.is_(True),
                    # Teachers watch their own lectures; ranking them with
                    # students would not mean much.
                    User.role == UserRole.STUDENT,
                )
            )
        ).all()
    }

    ranked = sorted(
        (
            (user, activity[user.id])
            for user in users.values()
            if activity[user.id].xp > 0
        ),
        # Ties go to whoever has more achievements, then by name for stability.
        key=lambda pair: (
            -pair[1].xp,
            -sum(item.unlocked for item in to_achievements(pair[1])),
            pair[0].first_name,
        ),
    )

    entries = [
        LeaderboardEntry(
            rank=rank,
            user=PublicUserResponse.model_validate(user),
            level=to_level(stats.xp),
            achievements=sum(item.unlocked for item in to_achievements(stats)),
        )
        for rank, (user, stats) in enumerate(ranked, start=1)
    ]

    return LeaderboardResponse(
        top=entries[:LEADERBOARD_SIZE],
        me=next((entry for entry in entries if entry.user.id == user_id), None),
    )

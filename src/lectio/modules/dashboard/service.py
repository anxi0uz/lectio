from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.exceptions import PermissionDeniedError
from lectio.models import (
    Bookmark,
    Enrollment,
    Favorite,
    Lecture,
    User,
    WatchProgress,
)
from lectio.models.enums import UserRole
from lectio.modules.auth.permissions import ensure_can_manage
from lectio.modules.bookmarks.schemas import BookmarkResponse
from lectio.modules.bookmarks.service import list_lecture_bookmarks
from lectio.modules.dashboard.schemas import (
    DashboardResponse,
    LectureStateResponse,
)
from lectio.modules.enrollments.service import is_enrolled
from lectio.modules.favorites.service import is_favorite
from lectio.modules.lectures.service import get_lecture_by_id
from lectio.modules.progress.service import (
    list_continue_watching,
    to_progress_response,
)
from lectio.modules.search.history import list_recent_searches

CONTINUE_WATCHING_ITEMS = 5
RECENT_SEARCHES = 5


async def _count(
    db: AsyncSession,
    model: type,
    *conditions: object,
) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(model).where(*conditions),  # pyright: ignore[reportArgumentType]
        )
        or 0
    )


async def get_dashboard(
    db: AsyncSession,
    user: User,
) -> DashboardResponse:
    completed, in_progress, watched = (
        await db.execute(
            select(
                func.count().filter(WatchProgress.completed_at.is_not(None)),
                func.count().filter(WatchProgress.completed_at.is_(None)),
                func.coalesce(func.sum(WatchProgress.position_seconds), 0.0),
            ).where(WatchProgress.user_id == user.id)
        )
    ).one()

    return DashboardResponse(
        enrolled_courses=await _count(db, Enrollment, Enrollment.user_id == user.id),
        lectures_completed=completed,
        lectures_in_progress=in_progress,
        watched_seconds=float(watched),
        favorites=await _count(db, Favorite, Favorite.user_id == user.id),
        bookmarks=await _count(db, Bookmark, Bookmark.user_id == user.id),
        lectures_uploaded=(
            await _count(db, Lecture, Lecture.owner_id == user.id)
            if user.role == UserRole.TEACHER
            else None
        ),
        continue_watching=await list_continue_watching(
            db,
            user.id,
            CONTINUE_WATCHING_ITEMS,
        ),
        recent_searches=await list_recent_searches(
            db,
            user.id,
            RECENT_SEARCHES,
        ),
    )


async def get_lecture_state(
    db: AsyncSession,
    user: User,
    lecture_id: UUID,
) -> LectureStateResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    try:
        ensure_can_manage(lecture.owner_id, user)
        can_manage = True
    except PermissionDeniedError:
        can_manage = False

    return LectureStateResponse(
        progress=to_progress_response(
            lecture_id,
            await db.get(WatchProgress, (user.id, lecture_id)),
        ),
        is_favorite=await is_favorite(db, user.id, lecture_id),
        is_enrolled_in_course=(
            lecture.course_id is not None
            and await is_enrolled(db, user.id, lecture.course_id)
        ),
        can_manage=can_manage,
        bookmarks=[
            BookmarkResponse.model_validate(bookmark)
            for bookmark in await list_lecture_bookmarks(db, user.id, lecture_id)
        ],
    )

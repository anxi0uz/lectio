from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Lecture, WatchProgress
from lectio.modules.lectures.schemas import LectureResponse
from lectio.modules.lectures.service import get_lecture_by_id
from lectio.modules.progress.schemas import (
    ContinueWatchingItem,
    ProgressResponse,
    ProgressUpdate,
)

log = structlog.get_logger(
    component="progress.service",
)

# Share of a lecture after which it counts as watched: the last minutes are
# usually goodbyes and questions.
COMPLETION_THRESHOLD = 0.9


def to_progress_response(
    lecture_id: UUID,
    progress: WatchProgress | None,
) -> ProgressResponse:
    if progress is None:
        return ProgressResponse(
            lecture_id=lecture_id,
            position_seconds=0.0,
            completed=False,
            updated_at=None,
        )

    return ProgressResponse(
        lecture_id=lecture_id,
        position_seconds=progress.position_seconds,
        completed=progress.completed_at is not None,
        updated_at=progress.updated_at,
    )


async def get_progress(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> ProgressResponse:
    await get_lecture_by_id(db, lecture_id)

    return to_progress_response(
        lecture_id,
        await db.get(WatchProgress, (user_id, lecture_id)),
    )


async def save_progress(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
    data: ProgressUpdate,
) -> ProgressResponse:
    lecture = await get_lecture_by_id(db, lecture_id)
    position = data.position_seconds

    if lecture.duration_seconds is not None:
        position = min(position, lecture.duration_seconds)

    progress = await db.get(WatchProgress, (user_id, lecture_id))

    if progress is None:
        progress = WatchProgress(
            user_id=user_id,
            lecture_id=lecture_id,
            position_seconds=position,
        )
        db.add(progress)

    progress.position_seconds = position

    if data.completed is not None:
        completed = data.completed
    else:
        # Rewinding a finished lecture keeps it finished.
        completed = progress.completed_at is not None or (
            lecture.duration_seconds is not None
            and position >= lecture.duration_seconds * COMPLETION_THRESHOLD
        )

    if completed and progress.completed_at is None:
        progress.completed_at = datetime.now(UTC)
        log.info(
            "lecture_completed",
            user_id=str(user_id),
            lecture_id=str(lecture_id),
        )
    elif not completed:
        progress.completed_at = None

    await db.flush()
    await db.refresh(progress)

    return to_progress_response(lecture_id, progress)


async def list_continue_watching(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
) -> list[ContinueWatchingItem]:
    rows = await db.execute(
        select(Lecture, WatchProgress)
        .join(WatchProgress, WatchProgress.lecture_id == Lecture.id)
        .where(
            WatchProgress.user_id == user_id,
            WatchProgress.completed_at.is_(None),
            WatchProgress.position_seconds > 0,
        )
        .order_by(WatchProgress.updated_at.desc())
        .limit(limit)
    )

    return [
        ContinueWatchingItem(
            lecture=LectureResponse.model_validate(lecture),
            position_seconds=progress.position_seconds,
            updated_at=progress.updated_at,
        )
        for lecture, progress in rows.all()
    ]

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Bookmark, Lecture
from lectio.modules.bookmarks.exceptions import (
    BookmarkNotFoundError,
    BookmarkOutOfRangeError,
)
from lectio.modules.bookmarks.schemas import (
    BookmarkCreate,
    BookmarkResponse,
    BookmarkUpdate,
    BookmarkWithLectureResponse,
)
from lectio.modules.lectures.service import get_lecture_by_id

log = structlog.get_logger(
    component="bookmarks.service",
)


def _ensure_within_lecture(
    lecture: Lecture,
    position_seconds: float,
) -> None:
    if (
        lecture.duration_seconds is not None
        and position_seconds > lecture.duration_seconds
    ):
        raise BookmarkOutOfRangeError


async def create_bookmark(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
    data: BookmarkCreate,
) -> Bookmark:
    lecture = await get_lecture_by_id(db, lecture_id)
    _ensure_within_lecture(lecture, data.position_seconds)

    bookmark = Bookmark(
        user_id=user_id,
        lecture_id=lecture_id,
        position_seconds=data.position_seconds,
        note=data.note or None,
    )

    db.add(bookmark)
    await db.flush()
    await db.refresh(bookmark)

    log.info(
        "bookmark_created",
        bookmark_id=str(bookmark.id),
        lecture_id=str(lecture_id),
    )

    return bookmark


async def list_lecture_bookmarks(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> list[Bookmark]:
    await get_lecture_by_id(db, lecture_id)

    bookmarks = await db.scalars(
        select(Bookmark)
        .where(
            Bookmark.user_id == user_id,
            Bookmark.lecture_id == lecture_id,
        )
        .order_by(
            Bookmark.position_seconds.asc(),
            Bookmark.created_at.asc(),
        )
    )

    return list(bookmarks.all())


async def list_user_bookmarks(
    db: AsyncSession,
    user_id: UUID,
) -> list[BookmarkWithLectureResponse]:
    rows = await db.execute(
        select(Bookmark, Lecture.title)
        .join(Lecture, Lecture.id == Bookmark.lecture_id)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
    )

    return [
        BookmarkWithLectureResponse(
            **BookmarkResponse.model_validate(bookmark).model_dump(),
            lecture_title=title,
        )
        for bookmark, title in rows.all()
    ]


async def get_own_bookmark(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
) -> Bookmark:
    bookmark = await db.get(Bookmark, bookmark_id)

    # Someone else's bookmark is reported as missing, not forbidden: its
    # existence is private too.
    if bookmark is None or bookmark.user_id != user_id:
        raise BookmarkNotFoundError

    return bookmark


async def update_bookmark(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
    data: BookmarkUpdate,
) -> Bookmark:
    bookmark = await get_own_bookmark(db, user_id, bookmark_id)
    updates = data.model_dump(exclude_unset=True)

    if updates.get("position_seconds") is not None:
        lecture = await get_lecture_by_id(db, bookmark.lecture_id)
        _ensure_within_lecture(lecture, updates["position_seconds"])
    else:
        updates.pop("position_seconds", None)

    if "note" in updates:
        updates["note"] = updates["note"] or None

    for field, value in updates.items():
        setattr(bookmark, field, value)

    await db.flush()
    await db.refresh(bookmark)

    return bookmark


async def delete_bookmark(
    db: AsyncSession,
    user_id: UUID,
    bookmark_id: UUID,
) -> None:
    bookmark = await get_own_bookmark(db, user_id, bookmark_id)

    await db.delete(bookmark)
    await db.flush()

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.exceptions import PermissionDeniedError
from lectio.models import Comment, Lecture, User
from lectio.modules.auth.permissions import ensure_can_manage
from lectio.modules.comments.exceptions import (
    CommentNotFoundError,
    CommentOutOfRangeError,
)
from lectio.modules.comments.schemas import CommentCreate, CommentResponse
from lectio.modules.lectures.service import get_lecture_by_id
from lectio.modules.users.schemas import PublicUserResponse

log = structlog.get_logger(
    component="comments.service",
)


def to_comment_response(
    comment: Comment,
    author: User,
) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        lecture_id=comment.lecture_id,
        author=PublicUserResponse.model_validate(author),
        text=comment.text,
        position_seconds=comment.position_seconds,
        created_at=comment.created_at,
    )


async def list_comments(
    db: AsyncSession,
    lecture_id: UUID,
) -> list[CommentResponse]:
    await get_lecture_by_id(db, lecture_id)

    rows = await db.execute(
        select(Comment, User)
        .join(User, User.id == Comment.user_id)
        .where(Comment.lecture_id == lecture_id)
        .order_by(Comment.created_at.desc())
    )

    return [to_comment_response(comment, author) for comment, author in rows.all()]


async def create_comment(
    db: AsyncSession,
    user: User,
    lecture_id: UUID,
    data: CommentCreate,
) -> CommentResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    if (
        data.position_seconds is not None
        and lecture.duration_seconds is not None
        and data.position_seconds > lecture.duration_seconds
    ):
        raise CommentOutOfRangeError

    comment = Comment(
        lecture_id=lecture_id,
        user_id=user.id,
        text=data.text,
        position_seconds=data.position_seconds,
    )

    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    log.info(
        "comment_created",
        comment_id=str(comment.id),
        lecture_id=str(lecture_id),
    )

    return to_comment_response(comment, user)


def _ensure_can_delete(
    comment: Comment,
    lecture: Lecture,
    user: User,
) -> None:
    """Authors delete their comments; teachers moderate their lectures."""
    if comment.user_id == user.id:
        return

    try:
        ensure_can_manage(lecture.owner_id, user)
    except PermissionDeniedError as error:
        raise PermissionDeniedError("Only the author can delete it") from error


async def delete_comment(
    db: AsyncSession,
    user: User,
    lecture_id: UUID,
    comment_id: UUID,
) -> None:
    lecture = await get_lecture_by_id(db, lecture_id)
    comment = await db.get(Comment, comment_id)

    if comment is None or comment.lecture_id != lecture_id:
        raise CommentNotFoundError

    _ensure_can_delete(comment, lecture, user)

    await db.delete(comment)
    await db.flush()

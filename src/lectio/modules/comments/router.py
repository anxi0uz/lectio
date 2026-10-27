from uuid import UUID

from fastapi import APIRouter, status

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.comments.schemas import CommentCreate, CommentResponse
from lectio.modules.comments.service import (
    create_comment,
    delete_comment,
    list_comments,
)

router = APIRouter(
    prefix="/lectures/{lecture_id}/comments",
    tags=["Comments"],
)


@router.get(
    "",
    response_model=list[CommentResponse],
)
async def list_comments_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> list[CommentResponse]:
    """Newest first."""
    return await list_comments(db, lecture_id)


@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment_endpoint(
    lecture_id: UUID,
    payload: CommentCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> CommentResponse:
    return await create_comment(db, current_user, lecture_id, payload)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment_endpoint(
    lecture_id: UUID,
    comment_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    """The author, or a teacher who manages the lecture."""
    await delete_comment(db, current_user, lecture_id, comment_id)

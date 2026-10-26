from uuid import UUID

from fastapi import APIRouter, status

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.bookmarks.schemas import (
    BookmarkCreate,
    BookmarkResponse,
    BookmarkUpdate,
    BookmarkWithLectureResponse,
)
from lectio.modules.bookmarks.service import (
    create_bookmark,
    delete_bookmark,
    list_lecture_bookmarks,
    list_user_bookmarks,
    update_bookmark,
)

router = APIRouter(
    tags=["Bookmarks"],
)


@router.post(
    "/lectures/{lecture_id}/bookmarks",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark_endpoint(
    lecture_id: UUID,
    payload: BookmarkCreate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> BookmarkResponse:
    bookmark = await create_bookmark(
        db,
        current_user.id,
        lecture_id,
        payload,
    )

    return BookmarkResponse.model_validate(bookmark)


@router.get(
    "/lectures/{lecture_id}/bookmarks",
    response_model=list[BookmarkResponse],
)
async def list_lecture_bookmarks_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> list[BookmarkResponse]:
    """The user's own bookmarks in a lecture, in playback order."""
    bookmarks = await list_lecture_bookmarks(db, current_user.id, lecture_id)

    return [BookmarkResponse.model_validate(bookmark) for bookmark in bookmarks]


@router.get(
    "/me/bookmarks",
    response_model=list[BookmarkWithLectureResponse],
)
async def list_my_bookmarks_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> list[BookmarkWithLectureResponse]:
    return await list_user_bookmarks(db, current_user.id)


@router.patch(
    "/bookmarks/{bookmark_id}",
    response_model=BookmarkResponse,
)
async def update_bookmark_endpoint(
    bookmark_id: UUID,
    payload: BookmarkUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> BookmarkResponse:
    bookmark = await update_bookmark(
        db,
        current_user.id,
        bookmark_id,
        payload,
    )

    return BookmarkResponse.model_validate(bookmark)


@router.delete(
    "/bookmarks/{bookmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_bookmark_endpoint(
    bookmark_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await delete_bookmark(db, current_user.id, bookmark_id)

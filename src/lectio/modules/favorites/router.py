from uuid import UUID

from fastapi import APIRouter, status

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.favorites.service import (
    add_favorite,
    list_favorites,
    remove_favorite,
)
from lectio.modules.lectures.schemas import LectureResponse

router = APIRouter(
    tags=["Favorites"],
)


@router.put(
    "/lectures/{lecture_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_favorite_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await add_favorite(db, current_user.id, lecture_id)


@router.delete(
    "/lectures/{lecture_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_favorite_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await remove_favorite(db, current_user.id, lecture_id)


@router.get(
    "/me/favorites",
    response_model=list[LectureResponse],
)
async def list_favorites_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> list[LectureResponse]:
    lectures = await list_favorites(db, current_user.id)

    return [LectureResponse.model_validate(lecture) for lecture in lectures]

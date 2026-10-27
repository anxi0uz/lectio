from uuid import UUID

from fastapi import APIRouter, status

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.likes.service import add_like, remove_like

router = APIRouter(
    prefix="/lectures/{lecture_id}/like",
    tags=["Likes"],
)


@router.put(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_like_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await add_like(db, current_user.id, lecture_id)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_like_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await remove_like(db, current_user.id, lecture_id)

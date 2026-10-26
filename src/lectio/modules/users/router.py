from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.users.schemas import (
    PublicUserResponse,
    UserResponse,
    UserUpdate,
)
from lectio.modules.users.service import (
    get_avatar_file,
    get_user_by_id,
    remove_avatar,
    set_avatar,
    update_user,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.patch(
    "/me",
    response_model=UserResponse,
)
async def update_me_endpoint(
    payload: UserUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> UserResponse:
    user = await update_user(db, current_user, payload)

    return UserResponse.model_validate(user)


@router.put(
    "/me/avatar",
    response_model=UserResponse,
)
async def set_avatar_endpoint(
    file: Annotated[UploadFile, File()],
    current_user: CurrentUserDep,
    db: SessionDep,
) -> UserResponse:
    user = await set_avatar(db, current_user, file)

    return UserResponse.model_validate(user)


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_avatar_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await remove_avatar(db, current_user)


@router.get(
    "/{user_id}",
    response_model=PublicUserResponse,
)
async def get_user_endpoint(
    user_id: UUID,
    db: SessionDep,
) -> PublicUserResponse:
    user = await get_user_by_id(db, user_id)

    return PublicUserResponse.model_validate(user)


@router.get(
    "/{user_id}/avatar",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}, "image/jpeg": {}}}},
)
async def get_avatar_endpoint(
    user_id: UUID,
    db: SessionDep,
) -> FileResponse:
    """Public, so it can be used directly in <img src>."""
    path, media_type = await get_avatar_file(db, user_id)

    return FileResponse(
        path,
        media_type=media_type,
    )

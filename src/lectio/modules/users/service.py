import asyncio
from pathlib import Path
from uuid import UUID

import anyio
import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.config import get_settings
from lectio.core.storage import avatars_dir, resolve_media_path, to_media_path
from lectio.models import User
from lectio.modules.users.exceptions import (
    AvatarNotFoundError,
    AvatarTooLargeError,
    InvalidAvatarError,
    UserNotFoundError,
)
from lectio.modules.users.schemas import UserUpdate

log = structlog.get_logger(
    component="users.service",
)

# The file's first bytes decide its type; names and Content-Type are
# whatever the client claims.
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
)
AVATAR_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
}


def detect_image_type(head: bytes) -> str | None:
    """Return the file extension for a supported image, or None."""
    for signature, suffix in IMAGE_SIGNATURES:
        if head.startswith(signature):
            return suffix

    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"

    return None


async def get_user_by_id(
    db: AsyncSession,
    user_id: UUID,
) -> User:
    user = await db.get(User, user_id)

    if user is None or not user.is_active:
        raise UserNotFoundError

    return user


async def update_user(
    db: AsyncSession,
    user: User,
    data: UserUpdate,
) -> User:
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        return user

    for field, value in updates.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    log.info(
        "user_updated",
        user_id=str(user.id),
        changed_fields=sorted(updates),
    )

    return user


def _remove_avatar_files(user_id: UUID) -> None:
    for path in avatars_dir().glob(f"{user_id}.*"):
        path.unlink(missing_ok=True)


async def set_avatar(
    db: AsyncSession,
    user: User,
    upload: UploadFile,
) -> User:
    limit = get_settings().max_avatar_mb * 1024 * 1024
    content = await upload.read(limit + 1)

    if len(content) > limit:
        raise AvatarTooLargeError(
            f"Avatar exceeds {get_settings().max_avatar_mb} MB",
        )

    suffix = detect_image_type(content[:16])

    if suffix is None:
        raise InvalidAvatarError

    await asyncio.to_thread(_remove_avatar_files, user.id)

    destination = avatars_dir() / f"{user.id}{suffix}"
    await anyio.Path(destination).write_bytes(content)

    user.avatar_path = to_media_path(destination)

    await db.flush()
    await db.refresh(user)

    log.info(
        "avatar_updated",
        user_id=str(user.id),
        size_bytes=len(content),
    )

    return user


async def remove_avatar(
    db: AsyncSession,
    user: User,
) -> None:
    await asyncio.to_thread(_remove_avatar_files, user.id)

    user.avatar_path = None
    await db.flush()


async def get_avatar_file(
    db: AsyncSession,
    user_id: UUID,
) -> tuple[Path, str]:
    user = await get_user_by_id(db, user_id)

    if user.avatar_path is None:
        raise AvatarNotFoundError

    path = resolve_media_path(user.avatar_path)

    if not path.is_file():
        raise AvatarNotFoundError

    return path, AVATAR_MEDIA_TYPES[path.suffix]

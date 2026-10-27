import asyncio
import mimetypes
import shutil
from pathlib import Path
from uuid import UUID

import anyio

from lectio.core.config import get_settings
from lectio.core.object_store import get_object_store

AUDIO_FILENAME = "audio.wav"
THUMBNAIL_FILENAME = "thumbnail.jpg"


def lecture_dir(lecture_id: UUID) -> Path:
    return get_settings().storage_dir / "lectures" / str(lecture_id)


def ensure_lecture_dir(lecture_id: UUID) -> Path:
    path = lecture_dir(lecture_id)
    path.mkdir(parents=True, exist_ok=True)

    return path


def avatars_dir() -> Path:
    path = get_settings().storage_dir / "avatars"
    path.mkdir(parents=True, exist_ok=True)

    return path


def resolve_media_path(relative: str) -> Path:
    return get_settings().storage_dir / relative


def to_media_path(path: Path) -> str:
    return str(path.relative_to(get_settings().storage_dir))


def content_type_for(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def remove_lecture_dir(lecture_id: UUID) -> None:
    shutil.rmtree(lecture_dir(lecture_id), ignore_errors=True)


async def locate_media(key: str) -> Path | str | None:
    """Where a stored file can be read: its local copy, else a signed link.

    A lecture's video stays local while it is processed and moves to the
    bucket afterwards, so both places are checked.
    """
    local = resolve_media_path(key)

    if local.is_file():
        return local

    store = get_object_store()

    if store is None or await store.size(key) is None:
        return None

    return store.signed_url(key)


async def fetch_media(key: str) -> Path | None:
    """A local copy of a stored file, downloaded from the bucket if needed."""
    local = resolve_media_path(key)

    if local.is_file():
        return local

    store = get_object_store()

    if store is None:
        return None

    local.parent.mkdir(parents=True, exist_ok=True)

    return local if await store.download(key, local) else None


async def move_to_store(path: Path) -> None:
    """Upload a finished file and drop the local copy; no-op for local storage."""
    store = get_object_store()

    if store is None or not await anyio.Path(path).is_file():
        return

    await store.upload(path, to_media_path(path), content_type_for(path))
    await anyio.Path(path).unlink(missing_ok=True)


async def remove_media_prefix(prefix: str) -> None:
    """Delete every bucket object whose key starts with the prefix."""
    store = get_object_store()

    if store is not None:
        await store.delete_prefix(prefix)


async def remove_lecture_files(lecture_id: UUID) -> None:
    await asyncio.to_thread(remove_lecture_dir, lecture_id)
    # The trailing slash keeps one lecture's prefix from matching another's.
    await remove_media_prefix(f"{to_media_path(lecture_dir(lecture_id))}/")

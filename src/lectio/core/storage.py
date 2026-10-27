import shutil
from pathlib import Path
from uuid import UUID

from lectio.core.config import get_settings

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


def remove_lecture_dir(lecture_id: UUID) -> None:
    shutil.rmtree(lecture_dir(lecture_id), ignore_errors=True)

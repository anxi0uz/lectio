import asyncio
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import anyio
import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.config import get_settings
from lectio.core.media import (
    MediaInfo,
    RemoteVideo,
    UrlProbeError,
    probe_media,
)
from lectio.core.storage import (
    ensure_lecture_dir,
    remove_lecture_dir,
    resolve_media_path,
    to_media_path,
)
from lectio.models import Lecture, User
from lectio.models.enums import (
    IN_PROGRESS_STATUSES,
    SEARCHABLE_STATUSES,
    LectureStatus,
    SourceType,
)
from lectio.modules.auth.permissions import ensure_can_manage
from lectio.modules.courses.service import get_course_by_id
from lectio.modules.lectures.exceptions import (
    FileTooLargeError,
    LectureBusyError,
    LectureNotFoundError,
    LectureNotReadyError,
    LiveStreamError,
    MediaTooLongError,
    NoAudioError,
    UnreadableMediaError,
    UnsupportedMediaError,
    UrlUnavailableError,
    VideoNotAvailableError,
)
from lectio.modules.lectures.schemas import LectureImport, LectureUpdate

log = structlog.get_logger(
    component="lectures.service",
)

MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}

UPLOAD_CHUNK_BYTES = 1024 * 1024

UrlProbe = Callable[[str], RemoteVideo]


def media_type_for(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


async def save_upload(
    upload: UploadFile,
    destination: Path,
) -> None:
    limit = get_settings().max_upload_mb * 1024 * 1024
    written = 0

    async with await anyio.open_file(destination, "wb") as file:
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            written += len(chunk)

            if written > limit:
                raise FileTooLargeError(
                    f"File exceeds {get_settings().max_upload_mb} MB",
                )

            await file.write(chunk)


def _ensure_duration_allowed(duration: float | None) -> None:
    limit_hours = get_settings().max_duration_hours

    if duration is not None and duration > limit_hours * 3600:
        raise MediaTooLongError(
            f"Recording is longer than {limit_hours:g} hours",
        )


async def validate_media_file(path: Path) -> MediaInfo:
    """Reject files the pipeline would fail on, before they enter the queue."""
    info = await probe_media(path)

    if info is None:
        raise UnreadableMediaError

    if not info.has_audio:
        raise NoAudioError

    _ensure_duration_allowed(info.duration)

    return info


async def validate_url(url: str, probe: UrlProbe) -> RemoteVideo:
    try:
        remote = await asyncio.wait_for(
            asyncio.to_thread(probe, url),
            timeout=get_settings().url_probe_timeout_seconds,
        )
    except (UrlProbeError, TimeoutError) as error:
        log.info(
            "url_rejected",
            url=url,
            reason=str(error)[:300],
        )
        raise UrlUnavailableError from error

    if remote.is_live:
        raise LiveStreamError

    _ensure_duration_allowed(remote.duration)

    return remote


async def _ensure_can_add_to_course(
    db: AsyncSession,
    course_id: UUID,
    user: User | None,
) -> None:
    course = await get_course_by_id(db, course_id)

    # The CLI imports without a user.
    if user is not None:
        ensure_can_manage(course.owner_id, user)


async def create_uploaded_lecture(
    db: AsyncSession,
    owner: User,
    upload: UploadFile,
    title: str | None,
    course_id: UUID | None,
) -> Lecture:
    filename = Path(upload.filename or "")
    suffix = filename.suffix.lower()

    if suffix not in MEDIA_TYPES:
        raise UnsupportedMediaError(
            f"Supported formats: {', '.join(sorted(MEDIA_TYPES))}",
        )

    if course_id is not None:
        await _ensure_can_add_to_course(db, course_id, owner)

    lecture_id = uuid4()
    destination = ensure_lecture_dir(lecture_id) / f"video{suffix}"

    try:
        await save_upload(upload, destination)
        info = await validate_media_file(destination)
    except BaseException:
        await asyncio.to_thread(remove_lecture_dir, lecture_id)
        raise

    lecture = Lecture(
        id=lecture_id,
        owner_id=owner.id,
        course_id=course_id,
        title=(title or filename.stem or "Untitled lecture")[:300],
        source_type=SourceType.UPLOAD,
        video_path=to_media_path(destination),
        video_mime_type=MEDIA_TYPES[suffix],
        duration_seconds=info.duration,
        status=LectureStatus.PENDING,
        progress=0.0,
    )

    db.add(lecture)
    await db.flush()
    await db.refresh(lecture)

    log.info(
        "lecture_uploaded",
        lecture_id=str(lecture.id),
        size_bytes=destination.stat().st_size,
    )

    return lecture


async def create_imported_lecture(
    db: AsyncSession,
    owner: User | None,
    data: LectureImport,
    probe: UrlProbe,
) -> Lecture:
    if data.course_id is not None:
        await _ensure_can_add_to_course(db, data.course_id, owner)

    url = str(data.url)
    remote = await validate_url(url, probe)

    lecture = Lecture(
        owner_id=owner.id if owner else None,
        course_id=data.course_id,
        title=(data.title or remote.title or url)[:300],
        duration_seconds=remote.duration,
        source_type=SourceType.URL,
        source_url=url,
        status=LectureStatus.PENDING,
        progress=0.0,
    )

    db.add(lecture)
    await db.flush()
    await db.refresh(lecture)

    log.info(
        "lecture_imported",
        lecture_id=str(lecture.id),
        source_url=url,
    )

    return lecture


async def list_lectures(
    db: AsyncSession,
    offset: int,
    limit: int,
    course_id: UUID | None = None,
    status: LectureStatus | None = None,
    owner_id: UUID | None = None,
) -> list[Lecture]:
    stmt = select(Lecture)

    if owner_id is not None:
        stmt = stmt.where(Lecture.owner_id == owner_id)

    if course_id is not None:
        stmt = stmt.where(Lecture.course_id == course_id)

    if status is not None:
        stmt = stmt.where(Lecture.status == status)

    lectures = await db.scalars(
        stmt.order_by(
            Lecture.created_at.desc(),
            Lecture.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(lectures.all())


async def get_lecture_by_id(
    db: AsyncSession,
    lecture_id: UUID,
) -> Lecture:
    lecture = await db.get(Lecture, lecture_id)

    if lecture is None:
        raise LectureNotFoundError

    return lecture


async def get_searchable_lecture(
    db: AsyncSession,
    lecture_id: UUID,
) -> Lecture:
    lecture = await get_lecture_by_id(db, lecture_id)

    if lecture.status not in SEARCHABLE_STATUSES:
        raise LectureNotReadyError

    return lecture


async def get_managed_lecture(
    db: AsyncSession,
    lecture_id: UUID,
    user: User,
) -> Lecture:
    lecture = await get_lecture_by_id(db, lecture_id)
    ensure_can_manage(lecture.owner_id, user)

    return lecture


async def update_lecture(
    db: AsyncSession,
    lecture_id: UUID,
    user: User,
    data: LectureUpdate,
) -> Lecture:
    lecture = await get_managed_lecture(db, lecture_id, user)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        return lecture

    if updates.get("course_id") is not None:
        await _ensure_can_add_to_course(db, updates["course_id"], user)

    if "title" in updates and updates["title"] is None:
        del updates["title"]

    for field, value in updates.items():
        setattr(lecture, field, value)

    await db.flush()
    await db.refresh(lecture)

    log.info(
        "lecture_updated",
        lecture_id=str(lecture.id),
        changed_fields=sorted(updates),
    )

    return lecture


async def restart_processing(
    db: AsyncSession,
    lecture_id: UUID,
    user: User,
) -> Lecture:
    lecture = await get_managed_lecture(db, lecture_id, user)

    if lecture.status in IN_PROGRESS_STATUSES:
        raise LectureBusyError

    lecture.status = LectureStatus.PENDING
    lecture.progress = 0.0
    lecture.error = None

    await db.flush()
    await db.refresh(lecture)

    log.info(
        "lecture_processing_restarted",
        lecture_id=str(lecture.id),
    )

    return lecture


async def delete_lecture(
    db: AsyncSession,
    lecture_id: UUID,
    user: User,
) -> None:
    lecture = await get_managed_lecture(db, lecture_id, user)

    await db.delete(lecture)
    await db.flush()
    await asyncio.to_thread(remove_lecture_dir, lecture_id)

    log.info(
        "lecture_deleted",
        lecture_id=str(lecture_id),
        deleted_by=str(user.id),
    )


def get_video_file(
    lecture: Lecture,
) -> tuple[Path, str]:
    if lecture.video_path is None:
        raise VideoNotAvailableError

    path = resolve_media_path(lecture.video_path)

    if not path.is_file():
        raise VideoNotAvailableError

    return path, lecture.video_mime_type or media_type_for(path)

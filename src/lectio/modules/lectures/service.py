import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import anyio
import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.config import get_settings
from lectio.core.storage import (
    ensure_lecture_dir,
    remove_lecture_dir,
    resolve_media_path,
    to_media_path,
)
from lectio.models import Lecture
from lectio.models.enums import (
    IN_PROGRESS_STATUSES,
    SEARCHABLE_STATUSES,
    LectureStatus,
    SourceType,
)
from lectio.modules.courses.service import get_course_by_id
from lectio.modules.lectures.exceptions import (
    FileTooLargeError,
    LectureBusyError,
    LectureNotFoundError,
    LectureNotReadyError,
    UnsupportedMediaError,
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


async def create_uploaded_lecture(
    db: AsyncSession,
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
        await get_course_by_id(db, course_id)

    lecture_id = uuid4()
    destination = ensure_lecture_dir(lecture_id) / f"video{suffix}"

    try:
        await save_upload(upload, destination)
    except BaseException:
        await asyncio.to_thread(remove_lecture_dir, lecture_id)
        raise

    lecture = Lecture(
        id=lecture_id,
        course_id=course_id,
        title=(title or filename.stem or "Untitled lecture")[:300],
        source_type=SourceType.UPLOAD,
        video_path=to_media_path(destination),
        video_mime_type=MEDIA_TYPES[suffix],
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
    data: LectureImport,
) -> Lecture:
    if data.course_id is not None:
        await get_course_by_id(db, data.course_id)

    url = str(data.url)

    lecture = Lecture(
        course_id=data.course_id,
        # The worker replaces it with the video title unless one was given.
        title=data.title or url[:300],
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
) -> list[Lecture]:
    stmt = select(Lecture)

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


async def update_lecture(
    db: AsyncSession,
    lecture_id: UUID,
    data: LectureUpdate,
) -> Lecture:
    lecture = await get_lecture_by_id(db, lecture_id)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        return lecture

    if updates.get("course_id") is not None:
        await get_course_by_id(db, updates["course_id"])

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
) -> Lecture:
    lecture = await get_lecture_by_id(db, lecture_id)

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
) -> None:
    lecture = await get_lecture_by_id(db, lecture_id)

    await db.delete(lecture)
    await db.flush()
    await asyncio.to_thread(remove_lecture_dir, lecture_id)

    log.info(
        "lecture_deleted",
        lecture_id=str(lecture_id),
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

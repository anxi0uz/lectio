import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, update
from structlog.contextvars import bound_contextvars

from lectio.core.config import get_settings
from lectio.core.jobs import Job, JobKind
from lectio.core.storage import (
    AUDIO_FILENAME,
    ensure_lecture_dir,
    resolve_media_path,
    to_media_path,
)
from lectio.db.session import get_session_factory
from lectio.ml.embedder import get_embedder, release_embedder
from lectio.ml.llm import get_llm
from lectio.ml.transcriber import get_transcriber, release_transcriber
from lectio.models import Chunk, Lecture
from lectio.models.enums import IN_PROGRESS_STATUSES, LectureStatus, SourceType
from lectio.modules.lectures.service import media_type_for
from lectio.modules.search.service import index_lecture
from lectio.modules.summaries.generator import generate_summary
from lectio.modules.summaries.service import save_summary
from lectio.modules.transcripts.service import load_segments, replace_segments
from lectio.worker.media import (
    MediaError,
    download_video,
    extract_audio,
    probe_duration,
)

log = structlog.get_logger(
    component="worker.pipeline",
)

# Progress is written at most this often, not on every Whisper segment.
PROGRESS_STEP = 0.02
ERROR_MAX_CHARS = 2000


class LectureGoneError(RuntimeError):
    """The lecture was deleted while it was being processed."""


async def update_lecture(
    lecture_id: UUID,
    **values: Any,
) -> None:
    async with get_session_factory()() as db:
        result = await db.execute(
            update(Lecture).where(Lecture.id == lecture_id).values(**values),
        )
        await db.commit()

    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise LectureGoneError


async def load_lecture(lecture_id: UUID) -> Lecture | None:
    async with get_session_factory()() as db:
        return await db.get(Lecture, lecture_id)


async def set_stage(
    lecture_id: UUID,
    status: LectureStatus,
) -> None:
    log.info("stage_started", stage=status.value)

    await update_lecture(
        lecture_id,
        status=status,
        progress=0.0,
    )


class ProgressReporter:
    """Thread-safe progress callback for blocking model code."""

    def __init__(
        self,
        lecture_id: UUID,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._lecture_id = lecture_id
        self._loop = loop
        self._last = 0.0

    def __call__(self, value: float) -> None:
        if value - self._last < PROGRESS_STEP and value < 1.0:
            return

        self._last = value
        asyncio.run_coroutine_threadsafe(
            self._write(round(min(max(value, 0.0), 1.0), 4)),
            self._loop,
        )

    async def _write(self, value: float) -> None:
        try:
            await update_lecture(self._lecture_id, progress=value)
        except LectureGoneError:
            pass


def _progress(lecture_id: UUID) -> Callable[[float], None]:
    return ProgressReporter(lecture_id, asyncio.get_running_loop())


async def run_job(job: Job) -> None:
    with bound_contextvars(
        job=job.kind.value,
        lecture_id=str(job.lecture_id),
    ):
        lecture = await load_lecture(job.lecture_id)

        if lecture is None:
            log.warning("job_skipped_lecture_missing")
            return

        try:
            match job.kind:
                case JobKind.PROCESS:
                    await process_lecture(lecture)
                case JobKind.SUMMARIZE:
                    await resummarize_lecture(lecture)
                case JobKind.REINDEX:
                    await reindex_lecture(lecture)
        except LectureGoneError:
            log.info("job_aborted_lecture_deleted")
        except Exception as error:
            log.exception("job_failed")

            try:
                await update_lecture(
                    job.lecture_id,
                    status=LectureStatus.FAILED,
                    error=f"{type(error).__name__}: {error}"[:ERROR_MAX_CHARS],
                )
            except LectureGoneError:
                pass


async def process_lecture(lecture: Lecture) -> None:
    # A duplicate job for a lecture that is already done is a no-op.
    if lecture.status not in IN_PROGRESS_STATUSES:
        log.info("job_skipped", status=lecture.status.value)
        return

    log.info("processing_started")

    directory = ensure_lecture_dir(lecture.id)
    video_path = resolve_media_path(lecture.video_path) if lecture.video_path else None

    if video_path is None or not video_path.is_file():
        if lecture.source_type != SourceType.URL or not lecture.source_url:
            raise MediaError("Lecture has neither a video file nor a source URL")

        video_path = await _download(lecture, directory)

    await set_stage(lecture.id, LectureStatus.EXTRACTING_AUDIO)

    audio_path = directory / AUDIO_FILENAME
    await extract_audio(video_path, audio_path)

    if lecture.duration_seconds is None:
        await update_lecture(
            lecture.id,
            duration_seconds=await probe_duration(video_path),
        )

    await _transcribe(lecture.id, audio_path)
    await _index(lecture.id)
    await _summarize(lecture)

    await update_lecture(
        lecture.id,
        status=LectureStatus.READY,
        progress=1.0,
        error=None,
    )

    # The transcript is stored; the WAV is only an intermediate artifact.
    audio_path.unlink(missing_ok=True)

    log.info("processing_finished")


async def _download(
    lecture: Lecture,
    directory: Path,
) -> Path:
    await set_stage(lecture.id, LectureStatus.DOWNLOADING)

    assert lecture.source_url is not None

    downloaded = await asyncio.to_thread(
        download_video,
        lecture.source_url,
        directory,
        _progress(lecture.id),
    )

    values: dict[str, Any] = {
        "video_path": to_media_path(downloaded.path),
        "video_mime_type": media_type_for(downloaded.path),
        "duration_seconds": downloaded.duration,
    }

    # The import endpoint stores the URL as a placeholder title.
    if downloaded.title and lecture.title == lecture.source_url[:300]:
        values["title"] = downloaded.title[:300]
        lecture.title = values["title"]

    await update_lecture(lecture.id, **values)

    return downloaded.path


async def _make_room_on_gpu() -> None:
    """Unload the LLM a chat request may have left in VRAM.

    Ollama adapts to whatever memory is free when it loads (spilling layers
    to the CPU), while Whisper and the embedder simply fail, so the worker
    takes the memory back before its own models load.
    """
    if get_settings().release_models_between_stages:
        await get_llm().unload()


async def _transcribe(
    lecture_id: UUID,
    audio_path: Path,
) -> None:
    await set_stage(lecture_id, LectureStatus.TRANSCRIBING)
    await _make_room_on_gpu()

    progress = _progress(lecture_id)

    # No local reference to the model: release_* can only free memory once
    # nothing else points at it.
    try:
        transcript = await asyncio.to_thread(
            lambda: get_transcriber().transcribe(audio_path, progress),
        )
    finally:
        if get_settings().release_models_between_stages:
            release_transcriber()

    if not transcript.segments:
        raise MediaError("No speech was recognized in the recording")

    async with get_session_factory()() as db:
        await replace_segments(db, lecture_id, transcript.segments)
        await db.execute(
            update(Lecture)
            .where(Lecture.id == lecture_id)
            .values(language=transcript.language)
        )
        await db.commit()

    log.info(
        "transcribed",
        segments=len(transcript.segments),
        language=transcript.language,
    )


async def _index(lecture_id: UUID) -> None:
    await set_stage(lecture_id, LectureStatus.INDEXING)
    await _make_room_on_gpu()

    try:
        await asyncio.to_thread(get_embedder)

        async with get_session_factory()() as db:
            segments = await load_segments(db, lecture_id)
            await index_lecture(db, get_embedder(), lecture_id, segments)
            await db.commit()
    finally:
        if get_settings().release_models_between_stages:
            release_embedder()


async def _summarize(lecture: Lecture) -> None:
    """Best effort: without an LLM the lecture is still searchable."""
    await set_stage(lecture.id, LectureStatus.SUMMARIZING)

    try:
        async with get_session_factory()() as db:
            chunks = list(
                (
                    await db.scalars(
                        select(Chunk)
                        .where(Chunk.lecture_id == lecture.id)
                        .order_by(Chunk.position.asc())
                    )
                ).all()
            )

            generated = await generate_summary(
                get_llm(),
                lecture.title,
                chunks,
                get_settings().llm_part_chars,
                _progress(lecture.id),
            )

            fresh = await db.get(Lecture, lecture.id)

            if fresh is None:
                raise LectureGoneError

            await save_summary(db, fresh, generated)
            await db.commit()
    except LectureGoneError:
        raise
    except Exception as error:
        log.exception("summary_failed")

        await update_lecture(
            lecture.id,
            summary_error=f"{type(error).__name__}: {error}"[:ERROR_MAX_CHARS],
        )


async def resummarize_lecture(lecture: Lecture) -> None:
    if lecture.status != LectureStatus.READY:
        log.info("job_skipped", status=lecture.status.value)
        return

    await _summarize(lecture)
    await update_lecture(
        lecture.id,
        status=LectureStatus.READY,
        progress=1.0,
    )


async def reindex_lecture(lecture: Lecture) -> None:
    if lecture.status != LectureStatus.READY:
        log.info("job_skipped", status=lecture.status.value)
        return

    await _index(lecture.id)
    await update_lecture(
        lecture.id,
        status=LectureStatus.READY,
        progress=1.0,
    )

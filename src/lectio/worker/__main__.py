import asyncio

import structlog
from sqlalchemy import select

from lectio.core.config import get_settings
from lectio.core.jobs import JobKind, dequeue_job, enqueue_job
from lectio.core.logger import configure_logging
from lectio.db.redis import close_redis, get_redis_client
from lectio.db.session import dispose_engine, get_session_factory
from lectio.ml.llm import close_llm
from lectio.models import Lecture
from lectio.models.enums import IN_PROGRESS_STATUSES, LectureStatus
from lectio.worker.pipeline import run_job

log = structlog.get_logger(
    component="worker",
)


async def requeue_unfinished() -> None:
    """Re-run lectures interrupted by a crash or restart.

    Duplicates are harmless: a job for a finished lecture is skipped.
    """
    async with get_session_factory()() as db:
        rows = (
            await db.execute(
                select(Lecture.id, Lecture.status)
                .where(Lecture.status.in_(IN_PROGRESS_STATUSES))
                .order_by(Lecture.created_at.asc())
            )
        ).all()

    for lecture_id, status in rows:
        # Summarizing comes after indexing: the transcript is already stored,
        # so only the summary has to be redone.
        kind = (
            JobKind.SUMMARIZE
            if status == LectureStatus.SUMMARIZING
            else JobKind.PROCESS
        )
        await enqueue_job(get_redis_client(), kind, lecture_id)

    if rows:
        log.info("unfinished_lectures_requeued", count=len(rows))


async def main() -> None:
    configure_logging(get_settings().debug)

    await requeue_unfinished()

    log.info("worker_started")

    # Ctrl+C or SIGTERM simply stop the process: an interrupted lecture keeps
    # its in-progress status and is picked up again on the next start.
    try:
        while True:
            job = await dequeue_job(get_redis_client())

            if job is not None:
                await run_job(job)
    finally:
        log.info("worker_stopping")

        await close_llm()
        await close_redis()
        await dispose_engine()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

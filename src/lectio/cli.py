import argparse
import asyncio
from pathlib import Path

import anyio
from pydantic import ValidationError
from sqlalchemy import select

from lectio.core.exceptions import DomainError
from lectio.core.jobs import JobKind, enqueue_job
from lectio.core.media import probe_url
from lectio.core.object_store import get_object_store
from lectio.core.storage import (
    THUMBNAIL_FILENAME,
    lecture_dir,
    move_to_store,
    remove_lecture_dir,
    resolve_media_path,
)
from lectio.db.redis import close_redis, get_redis_client
from lectio.db.session import dispose_engine, get_session_factory
from lectio.ml.llm import close_llm, get_llm
from lectio.models import Course, Lecture, User
from lectio.models.enums import IN_PROGRESS_STATUSES, LectureStatus
from lectio.modules.courses.schemas import CourseCreate
from lectio.modules.courses.service import create_course
from lectio.modules.lectures.schemas import LectureImport
from lectio.modules.lectures.service import create_imported_lecture
from lectio.modules.summaries.generator import suggest_questions
from lectio.modules.summaries.schemas import KeyTerm


def parse_seed_line(line: str) -> tuple[str, str | None] | None:
    """`URL` or `URL | Title`; blank lines and # comments are skipped."""
    line = line.strip()

    if not line or line.startswith("#"):
        return None

    url, _, title = line.partition("|")

    return url.strip(), title.strip() or None


async def seed(
    path: Path,
    course_title: str | None,
) -> None:
    entries = [
        entry
        for line in (await anyio.Path(path).read_text(encoding="utf-8")).splitlines()
        if (entry := parse_seed_line(line)) is not None
    ]

    async with get_session_factory()() as db:
        course_id = None

        if course_title:
            course = await db.scalar(
                select(Course).where(Course.title == course_title),
            )

            if course is None:
                course = await create_course(
                    db,
                    None,
                    CourseCreate(title=course_title),
                )

            course_id = course.id

        lectures: list[Lecture] = []

        for url, title in entries:
            try:
                data = LectureImport.model_validate(
                    {"url": url, "title": title, "course_id": course_id},
                )
            except ValidationError:
                print(f"skipped, not a URL: {url}")
                continue

            try:
                lecture = await create_imported_lecture(db, None, data, probe_url)
            except DomainError as error:
                print(f"skipped, {error.detail}: {url}")
                continue

            lectures.append(lecture)

        await db.commit()

    for lecture in lectures:
        await enqueue_job(get_redis_client(), JobKind.PROCESS, lecture.id)
        print(f"queued {lecture.id} {lecture.source_url}")


async def requeue_ready(kind: JobKind) -> None:
    async with get_session_factory()() as db:
        lecture_ids = list(
            (
                await db.scalars(
                    select(Lecture.id).where(
                        Lecture.status == LectureStatus.READY,
                    )
                )
            ).all()
        )

    for lecture_id in lecture_ids:
        await enqueue_job(get_redis_client(), kind, lecture_id)

    print(f"queued {kind.value} for {len(lecture_ids)} lectures")


async def move_storage() -> None:
    """Move files of finished lectures and avatars from the disk to the bucket.

    A local copy is deleted only after its upload succeeded.
    """
    store = get_object_store()

    if store is None:
        print("STORAGE_BACKEND is not s3, nothing to do")
        return

    await store.ensure_bucket()

    async with get_session_factory()() as db:
        lectures = (
            await db.execute(
                select(Lecture.id, Lecture.video_path).where(
                    Lecture.status.not_in(IN_PROGRESS_STATUSES),
                )
            )
        ).all()
        avatars = (
            await db.scalars(
                select(User.avatar_path).where(User.avatar_path.is_not(None)),
            )
        ).all()

    moved = 0

    for lecture_id, video_path in lectures:
        paths = [lecture_dir(lecture_id) / THUMBNAIL_FILENAME]
        if video_path:
            paths.append(resolve_media_path(video_path))

        for path in paths:
            if path.is_file():
                await move_to_store(path)
                moved += 1

        await asyncio.to_thread(remove_lecture_dir, lecture_id)

    for avatar_path in avatars:
        if avatar_path and resolve_media_path(avatar_path).is_file():
            await move_to_store(resolve_media_path(avatar_path))
            moved += 1

    print(f"moved {moved} files to the bucket")


async def fill_suggested_questions() -> None:
    """Generate chat questions for lectures summarized before they existed,
    without redoing their summaries."""
    llm = get_llm()

    async with get_session_factory()() as db:
        lectures = (
            await db.scalars(
                select(Lecture).where(
                    Lecture.status == LectureStatus.READY,
                    Lecture.summary.is_not(None),
                    Lecture.suggested_questions == [],
                )
            )
        ).all()

        for lecture in lectures:
            questions = await suggest_questions(
                llm,
                lecture.title,
                lecture.summary or "",
                [KeyTerm.model_validate(term) for term in lecture.key_terms],
            )
            lecture.suggested_questions = questions
            await db.commit()

            print(f"{len(questions)} questions for {lecture.title}")

    await close_llm()


async def run(args: argparse.Namespace) -> None:
    try:
        match args.command:
            case "seed":
                await seed(args.file, args.course)
            case "reindex":
                await requeue_ready(JobKind.REINDEX)
            case "resummarize":
                await requeue_ready(JobKind.SUMMARIZE)
            case "move-storage":
                await move_storage()
            case "suggest-questions":
                await fill_suggested_questions()
    finally:
        await close_redis()
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(prog="lectio")
    commands = parser.add_subparsers(dest="command", required=True)

    seed_parser = commands.add_parser(
        "seed",
        help="import lectures from a file with one `URL | title` per line",
    )
    seed_parser.add_argument("file", type=Path)
    seed_parser.add_argument("--course", help="course title to put them in")

    commands.add_parser(
        "reindex",
        help="rebuild embeddings of every processed lecture",
    )
    commands.add_parser(
        "resummarize",
        help="regenerate summaries of every processed lecture",
    )
    commands.add_parser(
        "suggest-questions",
        help="generate chat questions for lectures that have none",
    )
    commands.add_parser(
        "move-storage",
        help="move videos, previews and avatars from the disk to the bucket",
    )

    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()

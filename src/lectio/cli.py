import argparse
import asyncio
from pathlib import Path

import anyio
from pydantic import ValidationError
from sqlalchemy import select

from lectio.core.exceptions import DomainError
from lectio.core.jobs import JobKind, enqueue_job
from lectio.core.media import probe_url
from lectio.db.redis import close_redis, get_redis_client
from lectio.db.session import dispose_engine, get_session_factory
from lectio.models import Course, Lecture
from lectio.models.enums import LectureStatus
from lectio.modules.courses.schemas import CourseCreate
from lectio.modules.courses.service import create_course
from lectio.modules.lectures.schemas import LectureImport
from lectio.modules.lectures.service import create_imported_lecture


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


async def run(args: argparse.Namespace) -> None:
    try:
        match args.command:
            case "seed":
                await seed(args.file, args.course)
            case "reindex":
                await requeue_ready(JobKind.REINDEX)
            case "resummarize":
                await requeue_ready(JobKind.SUMMARIZE)
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

    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()

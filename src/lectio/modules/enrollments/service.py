from uuid import UUID

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Enrollment, Lecture, WatchProgress
from lectio.modules.courses.service import get_course_by_id, list_courses
from lectio.modules.enrollments.schemas import EnrolledCourseResponse

log = structlog.get_logger(
    component="enrollments.service",
)


async def enroll(
    db: AsyncSession,
    user_id: UUID,
    course_id: UUID,
) -> None:
    await get_course_by_id(db, course_id)

    await db.execute(
        insert(Enrollment)
        .values(user_id=user_id, course_id=course_id)
        .on_conflict_do_nothing()
    )

    log.info(
        "course_enrolled",
        user_id=str(user_id),
        course_id=str(course_id),
    )


async def unenroll(
    db: AsyncSession,
    user_id: UUID,
    course_id: UUID,
) -> None:
    await get_course_by_id(db, course_id)

    await db.execute(
        delete(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id,
        )
    )


async def list_enrolled_courses(
    db: AsyncSession,
    user_id: UUID,
) -> list[EnrolledCourseResponse]:
    enrollments = dict(
        (
            await db.execute(
                select(Enrollment.course_id, Enrollment.created_at).where(
                    Enrollment.user_id == user_id,
                )
            )
        ).all()
    )

    if not enrollments:
        return []

    completed = dict(
        (
            await db.execute(
                select(Lecture.course_id, func.count())
                .join(WatchProgress, WatchProgress.lecture_id == Lecture.id)
                .where(
                    WatchProgress.user_id == user_id,
                    WatchProgress.completed_at.is_not(None),
                    Lecture.course_id.in_(enrollments),
                )
                .group_by(Lecture.course_id)
            )
        ).all()
    )

    courses = await list_courses(db, course_ids=list(enrollments))
    result = [
        EnrolledCourseResponse(
            **course.model_dump(),
            enrolled_at=enrollments[course.id],
            completed_lectures=completed.get(course.id, 0),
            progress=(
                completed.get(course.id, 0) / course.lectures_count
                if course.lectures_count
                else 0.0
            ),
        )
        for course in courses
    ]

    return sorted(result, key=lambda course: course.enrolled_at, reverse=True)


async def is_enrolled(
    db: AsyncSession,
    user_id: UUID,
    course_id: UUID,
) -> bool:
    return await db.get(Enrollment, (user_id, course_id)) is not None

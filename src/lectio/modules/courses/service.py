from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Course
from lectio.modules.courses.exceptions import CourseNotFoundError
from lectio.modules.courses.schemas import CourseCreate

log = structlog.get_logger(
    component="courses.service",
)


async def create_course(
    db: AsyncSession,
    data: CourseCreate,
) -> Course:
    course = Course(**data.model_dump())

    db.add(course)
    await db.flush()
    await db.refresh(course)

    log.info(
        "course_created",
        course_id=str(course.id),
    )

    return course


async def list_courses(
    db: AsyncSession,
) -> list[Course]:
    courses = await db.scalars(
        select(Course).order_by(
            Course.created_at.asc(),
            Course.id.asc(),
        )
    )

    return list(courses.all())


async def get_course_by_id(
    db: AsyncSession,
    course_id: UUID,
) -> Course:
    course = await db.get(Course, course_id)

    if course is None:
        raise CourseNotFoundError

    return course


async def delete_course(
    db: AsyncSession,
    course_id: UUID,
) -> None:
    course = await get_course_by_id(db, course_id)

    await db.delete(course)
    await db.flush()

    log.info(
        "course_deleted",
        course_id=str(course_id),
    )

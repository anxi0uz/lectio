from uuid import UUID

import structlog
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Course, Lecture, User
from lectio.modules.auth.permissions import ensure_can_manage
from lectio.modules.courses.exceptions import CourseNotFoundError
from lectio.modules.courses.schemas import CourseCreate, CourseResponse

log = structlog.get_logger(
    component="courses.service",
)


def _with_stats() -> Select[Course, int, float]:
    """Courses with the number and total length of their lectures."""
    stats = (
        select(
            Lecture.course_id,
            func.count(Lecture.id).label("lectures_count"),
            func.coalesce(func.sum(Lecture.duration_seconds), 0.0).label(
                "total_duration_seconds",
            ),
        )
        .group_by(Lecture.course_id)
        .subquery()
    )

    return select(
        Course,
        func.coalesce(stats.c.lectures_count, 0),
        func.coalesce(stats.c.total_duration_seconds, 0.0),
    ).outerjoin(stats, stats.c.course_id == Course.id)


def to_course_response(
    course: Course,
    lectures_count: int,
    total_duration: float,
) -> CourseResponse:
    return CourseResponse.model_validate(course).model_copy(
        update={
            "lectures_count": lectures_count,
            "total_duration_seconds": float(total_duration),
        }
    )


async def create_course(
    db: AsyncSession,
    owner: User | None,
    data: CourseCreate,
) -> Course:
    course = Course(
        **data.model_dump(),
        owner_id=owner.id if owner else None,
    )

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
    owner_id: UUID | None = None,
    course_ids: list[UUID] | None = None,
) -> list[CourseResponse]:
    stmt = _with_stats()

    if owner_id is not None:
        stmt = stmt.where(Course.owner_id == owner_id)

    if course_ids is not None:
        stmt = stmt.where(Course.id.in_(course_ids))

    rows = await db.execute(
        stmt.order_by(
            Course.created_at.asc(),
            Course.id.asc(),
        )
    )

    return [to_course_response(*row) for row in rows.all()]


async def get_course_by_id(
    db: AsyncSession,
    course_id: UUID,
) -> Course:
    course = await db.get(Course, course_id)

    if course is None:
        raise CourseNotFoundError

    return course


async def get_course_details(
    db: AsyncSession,
    course_id: UUID,
) -> CourseResponse:
    row = (await db.execute(_with_stats().where(Course.id == course_id))).first()

    if row is None:
        raise CourseNotFoundError

    return to_course_response(*row)


async def delete_course(
    db: AsyncSession,
    course_id: UUID,
    user: User,
) -> None:
    course = await get_course_by_id(db, course_id)
    ensure_can_manage(course.owner_id, user)

    await db.delete(course)
    await db.flush()

    log.info(
        "course_deleted",
        course_id=str(course_id),
        deleted_by=str(user.id),
    )

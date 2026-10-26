from uuid import UUID

from fastapi import APIRouter, status

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.enrollments.schemas import EnrolledCourseResponse
from lectio.modules.enrollments.service import (
    enroll,
    list_enrolled_courses,
    unenroll,
)

router = APIRouter(
    tags=["Enrollments"],
)


@router.put(
    "/courses/{course_id}/enrollment",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def enroll_endpoint(
    course_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    """Idempotent: enrolling twice is not an error."""
    await enroll(db, current_user.id, course_id)


@router.delete(
    "/courses/{course_id}/enrollment",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unenroll_endpoint(
    course_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await unenroll(db, current_user.id, course_id)


@router.get(
    "/me/courses",
    response_model=list[EnrolledCourseResponse],
)
async def my_courses_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> list[EnrolledCourseResponse]:
    """Courses the user enrolled in, with how much of each is watched."""
    return await list_enrolled_courses(db, current_user.id)

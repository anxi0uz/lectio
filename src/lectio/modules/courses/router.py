from uuid import UUID

from fastapi import APIRouter, status

from lectio.api.dependencies import SessionDep
from lectio.modules.auth.dependencies import CurrentUserDep, TeacherDep
from lectio.modules.courses.schemas import CourseCreate, CourseResponse
from lectio.modules.courses.service import (
    create_course,
    delete_course,
    get_course_details,
    list_courses,
)

router = APIRouter(
    prefix="/courses",
    tags=["Courses"],
)


@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_endpoint(
    payload: CourseCreate,
    teacher: TeacherDep,
    db: SessionDep,
) -> CourseResponse:
    course = await create_course(db, teacher, payload)

    return CourseResponse.model_validate(course)


@router.get(
    "",
    response_model=list[CourseResponse],
)
async def list_courses_endpoint(
    db: SessionDep,
    owner_id: UUID | None = None,
) -> list[CourseResponse]:
    """All courses; with owner_id, those a teacher created."""
    return await list_courses(db, owner_id=owner_id)


@router.get(
    "/{course_id}",
    response_model=CourseResponse,
)
async def get_course_endpoint(
    course_id: UUID,
    db: SessionDep,
) -> CourseResponse:
    return await get_course_details(db, course_id)


@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_course_endpoint(
    course_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await delete_course(db, course_id, current_user)

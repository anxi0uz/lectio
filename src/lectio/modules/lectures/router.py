from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse, Response

from lectio.api.dependencies import RedisDep, SessionDep
from lectio.core.jobs import JobKind, enqueue_job
from lectio.core.media import probe_url
from lectio.models.enums import LectureStatus
from lectio.modules.auth.dependencies import CurrentUserDep, TeacherDep
from lectio.modules.lectures.schemas import (
    LectureImport,
    LectureResponse,
    LectureUpdate,
)
from lectio.modules.lectures.service import (
    UrlProbe,
    create_imported_lecture,
    create_uploaded_lecture,
    delete_lecture,
    ensure_thumbnail,
    get_lecture_by_id,
    get_video_source,
    list_lectures,
    restart_processing,
    update_lecture,
)

router = APIRouter(
    prefix="/lectures",
    tags=["Lectures"],
)


def get_url_probe() -> UrlProbe:
    return probe_url


UrlProbeDep = Annotated[
    UrlProbe,
    Depends(get_url_probe),
]

# Jobs are enqueued as background tasks: they run after the request's
# transaction is committed, so the worker always finds the lecture row.


@router.post(
    "",
    response_model=LectureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_lecture_endpoint(
    teacher: TeacherDep,
    db: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=300)] = None,
    course_id: Annotated[UUID | None, Form()] = None,
    allow_duplicate: Annotated[bool, Form()] = False,
) -> LectureResponse:
    lecture = await create_uploaded_lecture(
        db,
        teacher,
        file,
        title.strip() if title else None,
        course_id,
        allow_duplicate,
    )

    background_tasks.add_task(
        enqueue_job,
        redis,
        JobKind.PROCESS,
        lecture.id,
    )

    return LectureResponse.model_validate(lecture)


@router.post(
    "/import",
    response_model=LectureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_lecture_endpoint(
    payload: LectureImport,
    teacher: TeacherDep,
    probe: UrlProbeDep,
    db: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
) -> LectureResponse:
    lecture = await create_imported_lecture(db, teacher, payload, probe)

    background_tasks.add_task(
        enqueue_job,
        redis,
        JobKind.PROCESS,
        lecture.id,
    )

    return LectureResponse.model_validate(lecture)


@router.get(
    "",
    response_model=list[LectureResponse],
)
async def list_lectures_endpoint(
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    course_id: UUID | None = None,
    status: LectureStatus | None = None,
    owner_id: UUID | None = None,
) -> list[LectureResponse]:
    lectures = await list_lectures(
        db,
        offset,
        limit,
        course_id,
        status,
        owner_id,
    )

    return [LectureResponse.model_validate(lecture) for lecture in lectures]


@router.get(
    "/{lecture_id}",
    response_model=LectureResponse,
)
async def get_lecture_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> LectureResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    return LectureResponse.model_validate(lecture)


@router.patch(
    "/{lecture_id}",
    response_model=LectureResponse,
)
async def update_lecture_endpoint(
    lecture_id: UUID,
    payload: LectureUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> LectureResponse:
    lecture = await update_lecture(
        db,
        lecture_id,
        current_user,
        payload,
    )

    return LectureResponse.model_validate(lecture)


@router.post(
    "/{lecture_id}/reprocess",
    response_model=LectureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_lecture_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
) -> LectureResponse:
    lecture = await restart_processing(db, lecture_id, current_user)

    background_tasks.add_task(
        enqueue_job,
        redis,
        JobKind.PROCESS,
        lecture.id,
    )

    return LectureResponse.model_validate(lecture)


@router.delete(
    "/{lecture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_lecture_endpoint(
    lecture_id: UUID,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await delete_lecture(db, lecture_id, current_user)


@router.get(
    "/{lecture_id}/video",
    response_class=FileResponse,
    responses={
        200: {"content": {"video/mp4": {}}},
        206: {"description": "Partial content for a Range request"},
        307: {"description": "Signed link to the video in the bucket"},
    },
)
async def get_video_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> Response:
    lecture = await get_lecture_by_id(db, lecture_id)
    source, media_type = await get_video_source(lecture)

    if isinstance(source, str):
        # The bucket answers Range requests itself; players follow redirects.
        return RedirectResponse(source)

    # FileResponse answers Range requests, which players need for seeking.
    return FileResponse(
        source,
        media_type=media_type,
    )


@router.get(
    "/{lecture_id}/thumbnail",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def get_thumbnail_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> Response:
    """Preview frame for lecture cards; 404 for audio-only lectures."""
    lecture = await get_lecture_by_id(db, lecture_id)
    source = await ensure_thumbnail(lecture)

    if isinstance(source, str):
        # Signed links expire, so the redirect is cached for a short while.
        return RedirectResponse(
            source,
            headers={"Cache-Control": "private, max-age=600"},
        )

    return FileResponse(
        source,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

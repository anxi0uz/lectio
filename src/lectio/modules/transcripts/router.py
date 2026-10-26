from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response

from lectio.api.dependencies import SessionDep
from lectio.modules.transcripts.schemas import SegmentResponse
from lectio.modules.transcripts.service import list_segments, render_vtt

router = APIRouter(
    prefix="/lectures/{lecture_id}",
    tags=["Transcripts"],
)


@router.get(
    "/segments",
    response_model=list[SegmentResponse],
)
async def list_segments_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> list[SegmentResponse]:
    segments = await list_segments(db, lecture_id)

    return [SegmentResponse.model_validate(segment) for segment in segments]


@router.get(
    "/subtitles.vtt",
    response_class=Response,
    responses={200: {"content": {"text/vtt": {}}}},
)
async def get_subtitles_endpoint(
    lecture_id: UUID,
    db: SessionDep,
) -> Response:
    segments = await list_segments(db, lecture_id)

    return Response(
        render_vtt(segments),
        media_type="text/vtt; charset=utf-8",
    )

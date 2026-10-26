from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.ml.transcriber import TranscribedSegment
from lectio.models import Segment
from lectio.modules.lectures.service import get_searchable_lecture


async def list_segments(
    db: AsyncSession,
    lecture_id: UUID,
) -> list[Segment]:
    await get_searchable_lecture(db, lecture_id)

    return await load_segments(db, lecture_id)


async def load_segments(
    db: AsyncSession,
    lecture_id: UUID,
) -> list[Segment]:
    segments = await db.scalars(
        select(Segment)
        .where(Segment.lecture_id == lecture_id)
        .order_by(Segment.position.asc())
    )

    return list(segments.all())


async def replace_segments(
    db: AsyncSession,
    lecture_id: UUID,
    transcribed: Sequence[TranscribedSegment],
) -> None:
    await db.execute(
        delete(Segment).where(Segment.lecture_id == lecture_id),
    )

    db.add_all(
        Segment(
            lecture_id=lecture_id,
            position=position,
            start_seconds=segment.start,
            end_seconds=segment.end,
            text=segment.text,
        )
        for position, segment in enumerate(transcribed)
    )

    await db.flush()


def format_vtt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_part, milliseconds = divmod(milliseconds, 1000)

    return f"{hours:02}:{minutes:02}:{seconds_part:02}.{milliseconds:03}"


def render_vtt(segments: Sequence[Segment]) -> str:
    cues = [
        f"{segment.position + 1}\n"
        f"{format_vtt_timestamp(segment.start_seconds)} --> "
        f"{format_vtt_timestamp(segment.end_seconds)}\n"
        # A blank line ends a cue, and "-->" would start a new one.
        f"{' '.join(segment.text.split()).replace('-->', '->')}"
        for segment in segments
    ]

    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"

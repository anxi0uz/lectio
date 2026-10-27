from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import LectureLike
from lectio.modules.lectures.service import get_lecture_by_id


async def add_like(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> None:
    await get_lecture_by_id(db, lecture_id)

    await db.execute(
        insert(LectureLike)
        .values(user_id=user_id, lecture_id=lecture_id)
        .on_conflict_do_nothing()
    )


async def remove_like(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> None:
    await db.execute(
        delete(LectureLike).where(
            LectureLike.user_id == user_id,
            LectureLike.lecture_id == lecture_id,
        )
    )


async def is_liked(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> bool:
    return await db.get(LectureLike, (user_id, lecture_id)) is not None

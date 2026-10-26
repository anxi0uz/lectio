from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Favorite, Lecture
from lectio.modules.lectures.service import get_lecture_by_id


async def add_favorite(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> None:
    await get_lecture_by_id(db, lecture_id)

    await db.execute(
        insert(Favorite)
        .values(user_id=user_id, lecture_id=lecture_id)
        .on_conflict_do_nothing()
    )


async def remove_favorite(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> None:
    await db.execute(
        delete(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.lecture_id == lecture_id,
        )
    )


async def list_favorites(
    db: AsyncSession,
    user_id: UUID,
) -> list[Lecture]:
    lectures = await db.scalars(
        select(Lecture)
        .join(Favorite, Favorite.lecture_id == Lecture.id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
    )

    return list(lectures.all())


async def is_favorite(
    db: AsyncSession,
    user_id: UUID,
    lecture_id: UUID,
) -> bool:
    return await db.get(Favorite, (user_id, lecture_id)) is not None

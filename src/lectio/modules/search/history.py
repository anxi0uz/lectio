from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import SearchQuery
from lectio.modules.search.service import SearchScope


class RecentSearch(BaseModel):
    query: str
    searched_at: datetime


async def record_search(
    db: AsyncSession,
    user_id: UUID,
    query: str,
    scope: SearchScope,
) -> None:
    db.add(
        SearchQuery(
            user_id=user_id,
            query=query,
            lecture_id=scope.lecture_id,
            course_id=scope.course_id,
        )
    )
    await db.flush()


async def list_recent_searches(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
) -> list[RecentSearch]:
    """Distinct queries, most recent first; repeating one moves it up."""
    rows = await db.execute(
        select(
            SearchQuery.query,
            func.max(SearchQuery.created_at).label("searched_at"),
        )
        .where(SearchQuery.user_id == user_id)
        .group_by(SearchQuery.query)
        .order_by(func.max(SearchQuery.created_at).desc())
        .limit(limit)
    )

    return [
        RecentSearch(query=query, searched_at=searched_at)
        for query, searched_at in rows.all()
    ]


async def clear_search_history(
    db: AsyncSession,
    user_id: UUID,
) -> None:
    await db.execute(
        delete(SearchQuery).where(SearchQuery.user_id == user_id),
    )

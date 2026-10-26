from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from lectio.api.dependencies import (
    EmbedderDep,
    RerankerDep,
    SessionDep,
)
from lectio.modules.auth.dependencies import CurrentUserDep, OptionalUserDep
from lectio.modules.search.history import (
    RecentSearch,
    clear_search_history,
    list_recent_searches,
    record_search,
)
from lectio.modules.search.schemas import SearchHit, SearchQuery
from lectio.modules.search.service import SearchScope, search

router = APIRouter(
    tags=["Search"],
)


@router.get(
    "/search",
    response_model=list[SearchHit],
)
async def search_endpoint(
    q: Annotated[SearchQuery, Query()],
    db: SessionDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    current_user: OptionalUserDep,
    lecture_id: UUID | None = None,
    course_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SearchHit]:
    """Semantic search; without lecture_id or course_id it covers everything.

    Works without signing in; for a signed-in user the query is saved to
    their search history.
    """
    scope = SearchScope(
        lecture_id=lecture_id,
        course_id=course_id,
    )
    hits = await search(
        db,
        embedder,
        reranker,
        q,
        scope,
        limit,
    )

    if current_user is not None:
        await record_search(db, current_user.id, q, scope)

    return hits


@router.get(
    "/me/search-history",
    response_model=list[RecentSearch],
)
async def search_history_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[RecentSearch]:
    return await list_recent_searches(db, current_user.id, limit)


@router.delete(
    "/me/search-history",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_search_history_endpoint(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> None:
    await clear_search_history(db, current_user.id)

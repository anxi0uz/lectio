from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from lectio.api.dependencies import (
    EmbedderDep,
    RerankerDep,
    SessionDep,
)
from lectio.modules.search.schemas import SearchHit, SearchQuery
from lectio.modules.search.service import SearchScope, search

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


@router.get(
    "",
    response_model=list[SearchHit],
)
async def search_endpoint(
    q: Annotated[SearchQuery, Query()],
    db: SessionDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    lecture_id: UUID | None = None,
    course_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SearchHit]:
    """Semantic search; without lecture_id or course_id it covers everything."""
    return await search(
        db,
        embedder,
        reranker,
        q,
        SearchScope(
            lecture_id=lecture_id,
            course_id=course_id,
        ),
        limit,
    )

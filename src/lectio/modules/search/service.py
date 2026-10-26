import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from uuid import UUID

import structlog
from sqlalchemy import (
    ColumnElement,
    Float,
    cast,
    delete,
    func,
    literal,
    select,
)
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.config import get_settings
from lectio.ml.chunking import build_chunks
from lectio.ml.embedder import Embedder
from lectio.ml.reranker import Reranker
from lectio.models import Chunk, Lecture, Segment
from lectio.models.chunk import TEXT_SEARCH_CONFIG
from lectio.models.enums import SEARCHABLE_STATUSES
from lectio.modules.courses.service import get_course_by_id
from lectio.modules.lectures.service import get_searchable_lecture
from lectio.modules.search.schemas import SearchHit

log = structlog.get_logger(
    component="search.service",
)

# Candidates taken from each ranking before fusion.
CANDIDATES_PER_RANKING = 50
# Reciprocal Rank Fusion constant from the original paper.
RRF_K = 60
RERANK_POOL = 30

HIGHLIGHT_OPTIONS = (
    "StartSel=<mark>, StopSel=</mark>, "
    'MaxWords=45, MinWords=20, MaxFragments=2, FragmentDelimiter=" … "'
)


@dataclass(frozen=True, slots=True)
class SearchScope:
    lecture_id: UUID | None = None
    course_id: UUID | None = None


class _TimedSegment:
    """Adapts a stored segment to what the chunker expects."""

    __slots__ = ("start", "end", "text")

    def __init__(self, segment: Segment) -> None:
        self.start = segment.start_seconds
        self.end = segment.end_seconds
        self.text = segment.text


async def index_lecture(
    db: AsyncSession,
    embedder: Embedder,
    lecture_id: UUID,
    segments: Sequence[Segment],
) -> int:
    settings = get_settings()

    chunks = build_chunks(
        [_TimedSegment(segment) for segment in segments],
        target_seconds=settings.chunk_target_seconds,
        max_seconds=settings.chunk_max_seconds,
    )
    vectors = await asyncio.to_thread(
        embedder.embed,
        [chunk.text for chunk in chunks],
    )

    await db.execute(
        delete(Chunk).where(Chunk.lecture_id == lecture_id),
    )

    db.add_all(
        Chunk(
            lecture_id=lecture_id,
            position=position,
            start_seconds=chunk.start,
            end_seconds=chunk.end,
            text=chunk.text,
            embedding=vector,
        )
        for position, (chunk, vector) in enumerate(
            zip(chunks, vectors, strict=True),
        )
    )

    await db.flush()

    log.info(
        "lecture_indexed",
        lecture_id=str(lecture_id),
        chunks=len(chunks),
    )

    return len(chunks)


async def search(
    db: AsyncSession,
    embedder: Embedder,
    reranker: Reranker | None,
    query: str,
    scope: SearchScope,
    limit: int,
) -> list[SearchHit]:
    if scope.lecture_id is not None:
        await get_searchable_lecture(db, scope.lecture_id)

    if scope.course_id is not None:
        await get_course_by_id(db, scope.course_id)

    query_vector = await asyncio.to_thread(
        embedder.embed_query,
        query,
    )

    pool_size = max(limit, RERANK_POOL) if reranker else limit
    hits = await _hybrid_search(
        db,
        query,
        query_vector,
        scope,
        pool_size,
    )

    if reranker is not None and hits:
        scores = await asyncio.to_thread(
            reranker.score,
            query,
            [hit.text for hit in hits],
        )
        hits = [
            hit.model_copy(update={"score": score})
            for hit, score in sorted(
                zip(hits, scores, strict=True),
                key=lambda pair: pair[1],
                reverse=True,
            )
        ]

    return hits[:limit]


async def _hybrid_search(
    db: AsyncSession,
    query: str,
    query_vector: list[float],
    scope: SearchScope,
    limit: int,
) -> list[SearchHit]:
    filters: list[ColumnElement[bool]] = [
        Lecture.status.in_(SEARCHABLE_STATUSES),
    ]

    if scope.lecture_id is not None:
        filters.append(Chunk.lecture_id == scope.lecture_id)

    if scope.course_id is not None:
        filters.append(Lecture.course_id == scope.course_id)

    ts_query = func.websearch_to_tsquery(
        cast(TEXT_SEARCH_CONFIG, REGCONFIG),
        query,
    )
    distance = Chunk.embedding.cosine_distance(query_vector)
    text_rank = func.ts_rank_cd(Chunk.search_vector, ts_query)

    semantic = (
        select(
            Chunk.id.label("chunk_id"),
            func.row_number().over(order_by=distance).label("rank"),
        )
        .join(Lecture, Lecture.id == Chunk.lecture_id)
        .where(*filters)
        .order_by(distance)
        .limit(CANDIDATES_PER_RANKING)
        .cte("semantic")
    )

    lexical = (
        select(
            Chunk.id.label("chunk_id"),
            func.row_number().over(order_by=text_rank.desc()).label("rank"),
        )
        .join(Lecture, Lecture.id == Chunk.lecture_id)
        .where(
            *filters,
            Chunk.search_vector.bool_op("@@")(ts_query),
        )
        .order_by(text_rank.desc())
        .limit(CANDIDATES_PER_RANKING)
        .cte("lexical")
    )

    def rrf(rank: ColumnElement[int]) -> ColumnElement[float]:
        return func.coalesce(
            literal(1.0) / (RRF_K + cast(rank, Float)),
            0.0,
        )

    fused = (
        select(
            func.coalesce(
                semantic.c.chunk_id,
                lexical.c.chunk_id,
            ).label("chunk_id"),
            (rrf(semantic.c.rank) + rrf(lexical.c.rank)).label("score"),
        )
        .select_from(
            semantic.join(
                lexical,
                semantic.c.chunk_id == lexical.c.chunk_id,
                full=True,
            )
        )
        .cte("fused")
    )

    rows = await db.execute(
        select(
            Chunk,
            Lecture.title,
            fused.c.score,
            func.ts_headline(
                cast(TEXT_SEARCH_CONFIG, REGCONFIG),
                # Escaped first: the headline is meant to be rendered as HTML.
                func.replace(
                    func.replace(
                        func.replace(Chunk.text, "&", "&amp;"),
                        "<",
                        "&lt;",
                    ),
                    ">",
                    "&gt;",
                ),
                ts_query,
                HIGHLIGHT_OPTIONS,
            ),
        )
        .join(fused, fused.c.chunk_id == Chunk.id)
        .join(Lecture, Lecture.id == Chunk.lecture_id)
        .order_by(
            fused.c.score.desc(),
            Chunk.start_seconds.asc(),
        )
        .limit(limit)
    )

    return [
        SearchHit(
            chunk_id=chunk.id,
            lecture_id=chunk.lecture_id,
            lecture_title=title,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            text=chunk.text,
            highlight=highlight or escape(chunk.text),
            score=float(score),
        )
        for chunk, title, score, highlight in rows.all()
    ]

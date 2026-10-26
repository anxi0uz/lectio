import json
from collections.abc import AsyncIterator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.exceptions import DomainError
from lectio.ml.embedder import Embedder
from lectio.ml.llm import LLMClient
from lectio.ml.reranker import Reranker
from lectio.modules.qa.prompts import QA_SYSTEM
from lectio.modules.qa.schemas import AnswerResponse, QuestionRequest
from lectio.modules.search.schemas import SearchHit
from lectio.modules.search.service import SearchScope, search

log = structlog.get_logger(
    component="qa.service",
)

CONTEXT_HITS = 6
NO_CONTEXT_ANSWER = "Пока нет обработанных лекций, по которым можно ответить."


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02}:{secs:02}"

    return f"{minutes}:{secs:02}"


def format_sources(hits: list[SearchHit]) -> str:
    return "\n\n".join(
        f"[{number}] Лекция «{hit.lecture_title}», "
        f"{format_timestamp(hit.start_seconds)}–{format_timestamp(hit.end_seconds)}"
        f"\n{hit.text}"
        for number, hit in enumerate(hits, start=1)
    )


async def retrieve_context(
    db: AsyncSession,
    embedder: Embedder,
    reranker: Reranker | None,
    data: QuestionRequest,
) -> list[SearchHit]:
    hits = await search(
        db,
        embedder,
        reranker,
        data.question,
        SearchScope(
            lecture_id=data.lecture_id,
            course_id=data.course_id,
        ),
        CONTEXT_HITS,
    )

    # Sources follow the time line of the lecture, which reads better.
    hits.sort(key=lambda hit: (str(hit.lecture_id), hit.start_seconds))

    return hits


def build_messages(
    data: QuestionRequest,
    hits: list[SearchHit],
) -> list[dict[str, str]]:
    return [
        *(message.model_dump() for message in data.history),
        {
            "role": "user",
            "content": f"Фрагменты лекций:\n\n{format_sources(hits)}"
            f"\n\nВопрос: {data.question}",
        },
    ]


async def answer_question(
    db: AsyncSession,
    embedder: Embedder,
    reranker: Reranker | None,
    llm: LLMClient,
    data: QuestionRequest,
) -> AnswerResponse:
    hits = await retrieve_context(db, embedder, reranker, data)

    if not hits:
        return AnswerResponse(answer=NO_CONTEXT_ANSWER, sources=[])

    answer = await llm.complete(QA_SYSTEM, build_messages(data, hits))

    log.info(
        "question_answered",
        lecture_id=str(data.lecture_id) if data.lecture_id else None,
        sources=len(hits),
    )

    return AnswerResponse(
        answer=answer,
        sources=hits,
    )


def _event(name: str, payload: object) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_answer(
    llm: LLMClient,
    data: QuestionRequest,
    hits: list[SearchHit],
) -> AsyncIterator[str]:
    """Server-sent events: `sources` first, then `delta` pieces, then `done`.

    A failure after the response has started cannot change its status code,
    so it is reported as an `error` event instead.
    """
    yield _event("sources", [hit.model_dump(mode="json") for hit in hits])

    if not hits:
        yield _event("delta", {"text": NO_CONTEXT_ANSWER})
        yield _event("done", {})
        return

    try:
        async for piece in llm.stream(QA_SYSTEM, build_messages(data, hits)):
            yield _event("delta", {"text": piece})
    except DomainError as error:
        yield _event("error", {"detail": error.detail, "code": error.code})
        return

    log.info(
        "question_streamed",
        lecture_id=str(data.lecture_id) if data.lecture_id else None,
        sources=len(hits),
    )

    yield _event("done", {})

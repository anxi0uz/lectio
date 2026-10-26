import structlog
from sqlalchemy.ext.asyncio import AsyncSession

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


async def answer_question(
    db: AsyncSession,
    embedder: Embedder,
    reranker: Reranker | None,
    llm: LLMClient,
    data: QuestionRequest,
) -> AnswerResponse:
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

    if not hits:
        return AnswerResponse(
            answer="Пока нет обработанных лекций, по которым можно ответить.",
            sources=[],
        )

    # Sources follow the time line of the lecture, which reads better.
    hits.sort(key=lambda hit: (str(hit.lecture_id), hit.start_seconds))

    answer = await llm.complete(
        QA_SYSTEM,
        [
            *(message.model_dump() for message in data.history),
            {
                "role": "user",
                "content": f"Фрагменты лекций:\n\n{format_sources(hits)}"
                f"\n\nВопрос: {data.question}",
            },
        ],
    )

    log.info(
        "question_answered",
        lecture_id=str(data.lecture_id) if data.lecture_id else None,
        sources=len(hits),
    )

    return AnswerResponse(
        answer=answer,
        sources=hits,
    )

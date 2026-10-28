import html
from dataclasses import dataclass
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.bot.formatting import (
    format_answer,
    format_chapters,
    format_hits,
    lecture_url,
    link,
    markdown_to_html,
    split_message,
)
from lectio.core.media import probe_url
from lectio.ml.embedder import Embedder
from lectio.ml.llm import LLMClient
from lectio.ml.reranker import Reranker
from lectio.models import Lecture
from lectio.models.enums import LectureStatus
from lectio.modules.lectures.schemas import LectureImport
from lectio.modules.lectures.service import (
    UrlProbe,
    create_imported_lecture,
    get_lecture_by_id,
)
from lectio.modules.qa.schemas import QuestionRequest
from lectio.modules.qa.service import answer_question, format_timestamp
from lectio.modules.search.service import SearchScope, search
from lectio.modules.summaries.service import get_summary

log = structlog.get_logger(
    component="bot.service",
)

SEARCH_RESULTS = 5
RECENT_LECTURES = 10
MAX_QUESTION_BUTTONS = 4
GENERIC_QUESTION = "О чём эта лекция в двух словах?"
# A chat keeps its lecture for a month of silence.
CURRENT_LECTURE_TTL_SECONDS = 30 * 24 * 60 * 60
# How long "add it anyway" stays valid after a duplicate link.
PENDING_LINK_TTL_SECONDS = 60 * 60


def _current_key(chat_id: int) -> str:
    return f"bot:chat:{chat_id}:lecture"


def _pending_link_key(chat_id: int) -> str:
    return f"bot:chat:{chat_id}:pending_link"


async def set_current_lecture(
    redis: Redis,
    chat_id: int,
    lecture_id: UUID | None,
) -> None:
    if lecture_id is None:
        await redis.delete(_current_key(chat_id))
        return

    await redis.set(
        _current_key(chat_id),
        str(lecture_id),
        ex=CURRENT_LECTURE_TTL_SECONDS,
    )


async def get_current_lecture(
    redis: Redis,
    chat_id: int,
) -> UUID | None:
    value = await redis.get(_current_key(chat_id))

    if isinstance(value, bytes):
        value = value.decode()

    return UUID(value) if value else None


async def set_pending_link(
    redis: Redis,
    chat_id: int,
    url: str,
) -> None:
    # The link does not fit into 64 bytes of callback data, so the
    # "add anyway" button finds it here.
    await redis.set(
        _pending_link_key(chat_id),
        url,
        ex=PENDING_LINK_TTL_SECONDS,
    )


async def pop_pending_link(
    redis: Redis,
    chat_id: int,
) -> str | None:
    value = await redis.getdel(_pending_link_key(chat_id))

    if isinstance(value, bytes):
        value = value.decode()

    return value


async def import_lecture(
    db: AsyncSession,
    url: str,
    probe: UrlProbe = probe_url,
    allow_duplicate: bool = False,
) -> Lecture:
    """A lecture from a link sent to the bot; it has no owner, like seeded
    ones, so any teacher can manage it on the site."""
    return await create_imported_lecture(
        db,
        None,
        LectureImport.model_validate(
            {
                "url": url,
                "allow_duplicate": allow_duplicate,
            }
        ),
        probe,
    )


async def recent_lectures(db: AsyncSession) -> list[Lecture]:
    lectures = await db.scalars(
        select(Lecture)
        .where(Lecture.status == LectureStatus.READY)
        .order_by(Lecture.created_at.desc())
        .limit(RECENT_LECTURES)
    )

    return list(lectures.all())


@dataclass(frozen=True, slots=True)
class LectureCard:
    lecture_id: UUID
    messages: list[str]
    # Offered as buttons under the card.
    questions: list[str]


async def _questions(
    db: AsyncSession,
    lecture_id: UUID,
) -> list[str]:
    summary = await get_summary(db, lecture_id)

    return summary.suggested_questions[:MAX_QUESTION_BUTTONS] or [GENERIC_QUESTION]


async def lecture_card(
    db: AsyncSession,
    lecture_id: UUID,
) -> LectureCard:
    """The lecture's card: summary, then contents with links to moments."""
    lecture = await get_lecture_by_id(db, lecture_id)
    summary = await get_summary(db, lecture_id)

    header = (
        f"<b>{html.escape(lecture.title)}</b>\n"
        f"{format_timestamp(lecture.duration_seconds or 0)} · "
        + link("открыть в Lectio", lecture_url(lecture.id))
    )
    body = (
        markdown_to_html(summary.summary)
        if summary.summary
        else "Конспекта нет: языковая модель была недоступна. Поиск по лекции работает."
    )

    messages = split_message(f"{header}\n\n{body}")

    if summary.chapters:
        messages.extend(split_message(format_chapters(lecture.id, summary.chapters)))

    return LectureCard(
        lecture_id=lecture.id,
        messages=messages,
        questions=await _questions(db, lecture_id),
    )


async def suggested_question(
    db: AsyncSession,
    lecture_id: UUID,
    index: int,
) -> str | None:
    """A question by its button's position; buttons carry no text of their
    own, since Telegram allows only 64 bytes of data on them."""
    questions = await _questions(db, lecture_id)

    return questions[index] if 0 <= index < len(questions) else None


async def search_messages(
    db: AsyncSession,
    embedder: Embedder,
    reranker: Reranker | None,
    query: str,
) -> list[str]:
    hits = await search(
        db,
        embedder,
        reranker,
        query,
        SearchScope(),
        SEARCH_RESULTS,
    )

    return split_message(format_hits(hits))


async def answer_messages(
    db: AsyncSession,
    embedder: Embedder,
    reranker: Reranker | None,
    llm: LLMClient,
    question: str,
    lecture_id: UUID | None,
) -> list[str]:
    response = await answer_question(
        db,
        embedder,
        reranker,
        llm,
        QuestionRequest(question=question, lecture_id=lecture_id),
    )

    return split_message(format_answer(response.answer, response.sources))

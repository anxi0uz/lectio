from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Chapter, Lecture, User
from lectio.models.enums import LectureStatus
from lectio.modules.lectures.service import (
    get_lecture_by_id,
    get_managed_lecture,
)
from lectio.modules.summaries.exceptions import SummaryNotReadyError
from lectio.modules.summaries.generator import GeneratedSummary
from lectio.modules.summaries.schemas import (
    ChapterResponse,
    KeyTerm,
    SummaryResponse,
)


async def save_summary(
    db: AsyncSession,
    lecture: Lecture,
    generated: GeneratedSummary,
) -> None:
    await db.execute(
        delete(Chapter).where(Chapter.lecture_id == lecture.id),
    )

    entries = [
        (level, item)
        for section in generated.sections
        for level, item in [
            (1, section),
            *((2, sub) for sub in section.subsections),
        ]
    ]

    db.add_all(
        Chapter(
            lecture_id=lecture.id,
            position=position,
            level=level,
            title=item.title,
            start_seconds=item.start,
        )
        for position, (level, item) in enumerate(entries)
    )

    lecture.summary = generated.summary
    lecture.summary_error = None
    lecture.key_terms = [term.model_dump() for term in generated.key_terms]
    lecture.suggested_questions = generated.questions

    await db.flush()


async def get_summary(
    db: AsyncSession,
    lecture_id: UUID,
) -> SummaryResponse:
    lecture = await get_lecture_by_id(db, lecture_id)

    chapters = await db.scalars(
        select(Chapter)
        .where(Chapter.lecture_id == lecture_id)
        .order_by(Chapter.position.asc())
    )

    tree: list[ChapterResponse] = []

    for chapter in chapters.all():
        item = ChapterResponse.model_validate(chapter)

        if chapter.level == 2 and tree:
            tree[-1].subsections.append(item)
        else:
            tree.append(item)

    key_terms = [KeyTerm.model_validate(term) for term in lecture.key_terms]

    return SummaryResponse(
        lecture_id=lecture.id,
        status=lecture.status,
        summary=lecture.summary,
        error=lecture.summary_error,
        chapters=tree,
        key_terms=key_terms,
        suggested_questions=(
            lecture.suggested_questions or fallback_questions(tree, key_terms)
        ),
    )


def fallback_questions(
    chapters: list[ChapterResponse],
    terms: list[KeyTerm],
) -> list[str]:
    """Questions from the lecture's own terms and contents, for lectures
    summarized before questions were generated or when the model failed."""
    if not chapters and not terms:
        return []

    questions = [f"Что такое «{term.term}»?" for term in terms[:2]]

    # The first section is usually the introduction.
    if len(chapters) > 1:
        questions.append(f"Объясни подробнее: {chapters[1].title}")

    questions.append("Какие главные выводы этой лекции?")

    return questions


async def start_resummarize(
    db: AsyncSession,
    lecture_id: UUID,
    user: User,
) -> Lecture:
    lecture = await get_managed_lecture(db, lecture_id, user)

    if lecture.status != LectureStatus.READY:
        raise SummaryNotReadyError

    # Marked before the job runs, so clients see the lecture as busy and
    # keep polling even while the worker is still on another lecture.
    lecture.status = LectureStatus.SUMMARIZING
    lecture.progress = 0.0
    await db.flush()

    return lecture

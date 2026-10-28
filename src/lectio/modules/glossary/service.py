import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Lecture
from lectio.models.enums import SEARCHABLE_STATUSES
from lectio.modules.glossary.schemas import GlossaryEntry, TermMention
from lectio.modules.summaries.schemas import KeyTerm

SPACES = re.compile(r"\s+")


def term_key(term: str) -> str:
    """Spelling variants of one term ("Катет", "катет ", "ёмкость") match."""
    return SPACES.sub(" ", term.strip().casefold().replace("ё", "е"))


async def get_glossary(
    db: AsyncSession,
    query: str | None = None,
    course_id: UUID | None = None,
) -> list[GlossaryEntry]:
    """Key terms of all lectures, merged by term.

    Built from the terms each summary already stores, so a new or
    regenerated summary shows up here without any extra step.
    """
    stmt = select(
        Lecture.id,
        Lecture.title,
        Lecture.course_id,
        Lecture.key_terms,
    ).where(
        Lecture.status.in_(SEARCHABLE_STATUSES),
        func.jsonb_array_length(Lecture.key_terms) > 0,
    )

    if course_id is not None:
        stmt = stmt.where(Lecture.course_id == course_id)

    rows = await db.execute(
        stmt.order_by(
            Lecture.created_at.asc(),
            Lecture.id.asc(),
        )
    )

    entries: dict[str, GlossaryEntry] = {}

    for lecture_id, title, lecture_course_id, raw_terms in rows:
        for raw in raw_terms:
            term = KeyTerm.model_validate(raw)
            key = term_key(term.term)

            if not key:
                continue

            entry = entries.setdefault(
                key,
                GlossaryEntry(
                    term=term.term.strip(),
                    mentions=[],
                ),
            )

            # A summary may list a term twice; one mention per lecture.
            if any(mention.lecture_id == lecture_id for mention in entry.mentions):
                continue

            entry.mentions.append(
                TermMention(
                    lecture_id=lecture_id,
                    lecture_title=title,
                    course_id=lecture_course_id,
                    definition=term.definition,
                    start_seconds=term.start_seconds,
                )
            )

    if query and (needle := term_key(query)):
        entries = {
            key: entry
            for key, entry in entries.items()
            if needle in key
            or any(needle in term_key(m.definition) for m in entry.mentions)
        }

    return [entries[key] for key in sorted(entries)]

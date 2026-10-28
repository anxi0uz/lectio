from uuid import UUID

from pydantic import BaseModel


class TermMention(BaseModel):
    lecture_id: UUID
    lecture_title: str
    course_id: UUID | None
    definition: str
    start_seconds: float | None


class GlossaryEntry(BaseModel):
    term: str
    # Every lecture that explains the term, oldest first.
    mentions: list[TermMention]

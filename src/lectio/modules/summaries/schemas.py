from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lectio.models.enums import LectureStatus


class KeyTerm(BaseModel):
    term: str
    definition: str
    start_seconds: float | None = None


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    start_seconds: float
    subsections: list["ChapterResponse"] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    lecture_id: UUID
    status: LectureStatus
    # Markdown.
    summary: str | None
    error: str | None
    chapters: list[ChapterResponse]
    key_terms: list[KeyTerm]
    # Generated for this lecture, or built from its terms and contents.
    suggested_questions: list[str]


class _OutlineItem(BaseModel):
    title: str = Field(min_length=1)
    start: float


class OutlineSection(_OutlineItem):
    subsections: list[_OutlineItem] = Field(default_factory=list)


class PartDigest(BaseModel):
    """What the model returns for one part of a transcript."""

    summary: str = ""
    sections: list[OutlineSection] = Field(default_factory=list)
    terms: list[KeyTerm] = Field(default_factory=list)


class Outline(BaseModel):
    sections: list[OutlineSection] = Field(default_factory=list)

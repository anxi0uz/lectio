from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

SearchQuery = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=500,
    ),
]


class SearchHit(BaseModel):
    chunk_id: UUID
    lecture_id: UUID
    lecture_title: str
    start_seconds: float
    end_seconds: float
    text: str
    # Fragment of `text` with matched words wrapped in <mark></mark>.
    highlight: str
    score: float

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.ml.transcriber import TranscribedSegment
from lectio.models import Lecture
from lectio.models.chunk import EMBEDDING_DIM
from lectio.models.enums import LectureStatus, SourceType
from lectio.modules.search.service import index_lecture
from lectio.modules.transcripts.service import load_segments, replace_segments

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

WORD = re.compile(r"\w+")


def alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


@dataclass(frozen=True, slots=True)
class RegisteredUser:
    id: str
    email: str
    access_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
        }


class RegisterUser(Protocol):
    async def __call__(
        self,
        email: str,
        role: str = "student",
        password: str = "test-password",
        first_name: str = "Test",
        last_name: str = "User",
    ) -> RegisteredUser: ...


class FakeEmbedder:
    """Bag of word prefixes hashed into a vector: texts sharing words are close.

    Stands in for BGE-M3 so tests run without downloading models.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM

        for word in WORD.findall(text.casefold()):
            digest = hashlib.blake2b(word[:5].encode(), digest_size=4).digest()
            vector[int.from_bytes(digest) % EMBEDDING_DIM] += 1.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0

        return [value / norm for value in vector]


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
    ) -> str:
        self.calls.append((system, messages))

        return "Ответ по лекции [1]."

    async def close(self) -> None:
        pass


async def create_processed_lecture(
    db: AsyncSession,
    title: str,
    phrases: list[str],
    course_id: UUID | None = None,
    seconds_per_phrase: float = 10.0,
) -> Lecture:
    """A lecture as the worker leaves it: transcript stored and indexed."""
    lecture = Lecture(
        title=title,
        course_id=course_id,
        source_type=SourceType.UPLOAD,
        status=LectureStatus.READY,
        progress=1.0,
        duration_seconds=len(phrases) * seconds_per_phrase,
        language="ru",
    )
    db.add(lecture)
    await db.flush()

    await replace_segments(
        db,
        lecture.id,
        [
            TranscribedSegment(
                start=index * seconds_per_phrase,
                end=(index + 1) * seconds_per_phrase,
                text=phrase,
            )
            for index, phrase in enumerate(phrases)
        ],
    )
    await index_lecture(
        db,
        FakeEmbedder(),  # pyright: ignore[reportArgumentType]
        lecture.id,
        await load_segments(db, lecture.id),
    )
    await db.commit()

    return lecture

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models.enums import LectureStatus
from tests.support import create_processed_lecture

pytestmark = pytest.mark.anyio


async def test_glossary_merges_terms_across_lectures(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    geometry = await create_processed_lecture(db, "Геометрия", ["Катет."])
    geometry.key_terms = [
        {"term": "Катет", "definition": "сторона у прямого угла", "start_seconds": 5},
        {"term": "Гипотенуза", "definition": "сторона напротив прямого угла"},
    ]
    trigonometry = await create_processed_lecture(db, "Тригонометрия", ["Синус."])
    trigonometry.key_terms = [
        {"term": "катет ", "definition": "часть треугольника", "start_seconds": 40},
        {"term": "Синус", "definition": "отношение катета к гипотенузе"},
    ]
    unfinished = await create_processed_lecture(db, "Черновик", ["Ёмкость."])
    unfinished.key_terms = [{"term": "Ёмкость", "definition": "черновик"}]
    unfinished.status = LectureStatus.TRANSCRIBING
    await db.commit()

    glossary = (await client.get("/api/v1/glossary")).json()

    assert [entry["term"] for entry in glossary] == ["Гипотенуза", "Катет", "Синус"]

    cathetus = glossary[1]

    assert [m["lecture_title"] for m in cathetus["mentions"]] == [
        "Геометрия",
        "Тригонометрия",
    ]
    assert cathetus["mentions"][1]["start_seconds"] == 40

    # Matches the term itself or any of its definitions.
    found = (await client.get("/api/v1/glossary", params={"q": "катет"})).json()

    assert [entry["term"] for entry in found] == ["Катет", "Синус"]

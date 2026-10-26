import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.core.jobs import JOBS_QUEUE_KEY
from lectio.modules.summaries.generator import GeneratedSummary
from lectio.modules.summaries.schemas import KeyTerm, OutlineSection
from lectio.modules.summaries.service import save_summary
from tests.support import create_processed_lecture

pytestmark = pytest.mark.anyio


async def test_summary_tree_and_regeneration(
    client: AsyncClient,
    db: AsyncSession,
    test_redis: Redis,
) -> None:
    lecture = await create_processed_lecture(
        db,
        "Лекция",
        ["Первая мысль.", "Вторая мысль.", "Третья мысль.", "Итоги."],
    )
    url = f"/api/v1/lectures/{lecture.id}/summary"

    empty = await client.get(url)

    assert empty.json()["summary"] is None
    assert empty.json()["chapters"] == []

    await save_summary(
        db,
        lecture,
        GeneratedSummary(
            summary="## Главное\n- мысль",
            sections=[
                OutlineSection.model_validate(
                    {
                        "title": "Начало",
                        "start": 0,
                        "subsections": [
                            {"title": "Первая", "start": 0},
                            {"title": "Вторая", "start": 10},
                        ],
                    }
                ),
                OutlineSection(title="Итоги", start=30),
            ],
            key_terms=[
                KeyTerm(term="Мысль", definition="То, что думают", start_seconds=0)
            ],
        ),
    )
    await db.commit()

    filled = (await client.get(url)).json()

    assert filled["summary"] == "## Главное\n- мысль"
    assert [chapter["title"] for chapter in filled["chapters"]] == ["Начало", "Итоги"]
    assert [sub["title"] for sub in filled["chapters"][0]["subsections"]] == [
        "Первая",
        "Вторая",
    ]
    assert filled["chapters"][1]["start_seconds"] == 30
    assert filled["key_terms"] == [
        {"term": "Мысль", "definition": "То, что думают", "start_seconds": 0.0},
    ]

    regenerate = await client.post(url)

    assert regenerate.status_code == 202
    assert await test_redis.llen(JOBS_QUEUE_KEY) == 1  # pyright: ignore[reportGeneralTypeIssues]

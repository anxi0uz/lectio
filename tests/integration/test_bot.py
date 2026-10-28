import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.bot.service import (
    answer_messages,
    get_current_lecture,
    import_lecture,
    lecture_card,
    pop_pending_link,
    search_messages,
    set_current_lecture,
    set_pending_link,
    suggested_question,
)
from lectio.core.exceptions import DomainError
from lectio.models.enums import LectureStatus
from lectio.modules.lectures.exceptions import DuplicateLectureError
from lectio.modules.summaries.generator import GeneratedSummary
from lectio.modules.summaries.schemas import OutlineSection
from lectio.modules.summaries.service import save_summary
from tests.support import (
    FakeEmbedder,
    FakeLLM,
    create_processed_lecture,
    fake_url_probe,
)

pytestmark = pytest.mark.anyio


async def test_lecture_card_search_and_answer(
    db: AsyncSession,
    test_redis: Redis,
) -> None:
    lecture = await create_processed_lecture(
        db,
        "Теорема Пифагора",
        ["Катет прилегает к прямому углу.", "Гипотенуза лежит напротив."],
    )
    await save_summary(
        db,
        lecture,
        GeneratedSummary(
            summary="## Главное\n- **Катет** и гипотенуза",
            sections=[OutlineSection(title="Стороны", start=10)],
            key_terms=[],
            questions=["Что такое катет?"],
        ),
    )
    await db.commit()

    card = await lecture_card(db, lecture.id)
    text = "\n".join(card.messages)

    assert "<b>Теорема Пифагора</b>" in text
    assert "• <b>Катет</b> и гипотенуза" in text
    assert f"/lectures/{lecture.id}?t=10" in text
    assert card.questions == ["Что такое катет?"]
    assert await suggested_question(db, lecture.id, 0) == "Что такое катет?"
    assert await suggested_question(db, lecture.id, 5) is None

    found = "\n".join(
        await search_messages(db, FakeEmbedder(), None, "гипотенуза напротив")  # pyright: ignore[reportArgumentType]
    )

    assert "Теорема Пифагора" in found
    assert "<b>Гипотенуза</b>" in found

    answer = "\n".join(
        await answer_messages(
            db,
            FakeEmbedder(),  # pyright: ignore[reportArgumentType]
            None,
            FakeLLM(),  # pyright: ignore[reportArgumentType]
            "Что такое катет?",
            lecture.id,
        )
    )

    # The first fragment starts at 0:00, so its link has no ?t=.
    assert f'/lectures/{lecture.id}">[1]</a>' in answer
    assert "<b>Источники</b>" in answer

    assert await get_current_lecture(test_redis, 42) is None

    await set_current_lecture(test_redis, 42, lecture.id)

    assert await get_current_lecture(test_redis, 42) == lecture.id

    await set_current_lecture(test_redis, 42, None)

    assert await get_current_lecture(test_redis, 42) is None


async def test_import_from_link(
    db: AsyncSession,
) -> None:
    lecture = await import_lecture(db, "https://youtu.be/lecture", fake_url_probe)

    assert lecture.status == LectureStatus.PENDING
    assert lecture.owner_id is None
    assert lecture.title == "Видео со страницы"

    with pytest.raises(DomainError) as error:
        await import_lecture(db, "https://youtu.be/missing", fake_url_probe)

    assert error.value.code == "url_unavailable"


async def test_repeated_link_offers_the_existing_lecture(
    db: AsyncSession,
    test_redis: Redis,
) -> None:
    url = "https://www.youtube.com/watch?v=same"
    first = await import_lecture(db, url, fake_url_probe)

    with pytest.raises(DuplicateLectureError) as error:
        await import_lecture(db, f"{url}&t=30", fake_url_probe)

    again = await import_lecture(db, url, fake_url_probe, allow_duplicate=True)

    assert error.value.lecture_id == first.id
    assert again.id != first.id

    await set_pending_link(test_redis, 42, url)

    assert await pop_pending_link(test_redis, 42) == url
    # One press of "add anyway" per link.
    assert await pop_pending_link(test_redis, 42) is None

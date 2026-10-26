import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Course
from tests.support import FakeLLM, create_processed_lecture

pytestmark = pytest.mark.anyio

GEOMETRY = [
    "Сегодня мы докажем теорему Пифагора.",
    "Квадрат гипотенузы равен сумме квадратов катетов.",
    "Рассмотрим площадь большого квадрата со стороной a плюс b.",
    "Он состоит из четырёх треугольников и маленького квадрата.",
    "Отсюда и следует утверждение теоремы.",
]

BIOLOGY = [
    "Клетка является основной единицей жизни.",
    "Митохондрии вырабатывают энергию для клетки.",
    "Ядро хранит генетическую информацию.",
]


async def test_segments_and_subtitles(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    lecture = await create_processed_lecture(db, "Теорема Пифагора", GEOMETRY)

    segments = await client.get(f"/api/v1/lectures/{lecture.id}/segments")
    subtitles = await client.get(f"/api/v1/lectures/{lecture.id}/subtitles.vtt")
    details = await client.get(f"/api/v1/lectures/{lecture.id}")

    assert [item["text"] for item in segments.json()] == GEOMETRY
    assert segments.json()[1]["start_seconds"] == 10.0
    assert subtitles.headers["content-type"].startswith("text/vtt")
    assert subtitles.text.startswith("WEBVTT\n\n1\n00:00:00.000 --> 00:00:10.000\n")
    assert "00:00:40.000 --> 00:00:50.000\nОтсюда" in subtitles.text
    assert details.json()["subtitles_url"].endswith("/subtitles.vtt")


async def test_search_ranks_matching_fragment_first(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    geometry = await create_processed_lecture(db, "Теорема Пифагора", GEOMETRY)
    await create_processed_lecture(db, "Клетка", BIOLOGY)

    everywhere = await client.get(
        "/api/v1/search",
        params={"q": "энергия митохондрий"},
    )
    in_lecture = await client.get(
        "/api/v1/search",
        params={"q": "сумма квадратов катетов", "lecture_id": str(geometry.id)},
    )

    assert everywhere.status_code == 200
    assert everywhere.json()[0]["lecture_title"] == "Клетка"
    assert "<mark>" in everywhere.json()[0]["highlight"]

    hits = in_lecture.json()

    assert {hit["lecture_id"] for hit in hits} == {str(geometry.id)}
    assert "катетов" in hits[0]["text"]
    assert hits[0]["start_seconds"] <= 10.0 < hits[0]["end_seconds"]


async def test_search_scopes_and_validation(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    course = Course(title="Математика")
    db.add(course)
    await db.flush()

    await create_processed_lecture(db, "Пифагор", GEOMETRY, course_id=course.id)
    await create_processed_lecture(db, "Клетка", BIOLOGY)

    in_course = await client.get(
        "/api/v1/search",
        params={"q": "клетка", "course_id": str(course.id)},
    )
    empty_query = await client.get("/api/v1/search", params={"q": "   "})
    missing_lecture = await client.get(
        "/api/v1/search",
        params={"q": "x", "lecture_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert {hit["lecture_title"] for hit in in_course.json()} == {"Пифагор"}
    assert empty_query.status_code == 422
    assert missing_lecture.status_code == 404


async def test_highlight_escapes_html(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    await create_processed_lecture(db, "HTML", ["Тег <script> опасен"])

    response = await client.get("/api/v1/search", params={"q": "тег"})

    assert "<script>" not in response.json()[0]["highlight"]
    assert "&lt;script&gt;" in response.json()[0]["highlight"]


async def test_question_answering_cites_sources(
    client: AsyncClient,
    db: AsyncSession,
    fake_llm: FakeLLM,
) -> None:
    lecture = await create_processed_lecture(db, "Теорема Пифагора", GEOMETRY)

    response = await client.post(
        "/api/v1/qa",
        json={
            "question": "Чему равен квадрат гипотенузы?",
            "lecture_id": str(lecture.id),
            "history": [
                {"role": "user", "content": "Привет"},
                {"role": "assistant", "content": "Здравствуйте"},
            ],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["answer"] == "Ответ по лекции [1]."
    assert payload["sources"]
    assert [source["start_seconds"] for source in payload["sources"]] == sorted(
        source["start_seconds"] for source in payload["sources"]
    )

    _, messages = fake_llm.calls[0]

    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert "[1] Лекция «Теорема Пифагора», 0:00–" in messages[-1]["content"]
    assert messages[-1]["content"].endswith("Вопрос: Чему равен квадрат гипотенузы?")

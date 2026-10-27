import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models.enums import LectureStatus
from tests.support import FakeLLM, RegisteredUser, create_processed_lecture

pytestmark = pytest.mark.anyio


async def test_quiz_generation_and_storage(
    client: AsyncClient,
    db: AsyncSession,
    fake_llm: FakeLLM,
    student: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(
        db,
        "Лекция",
        ["Первая мысль о началах.", "Вторая мысль.", "Третья мысль.", "Итоги."],
    )
    url = f"/api/v1/lectures/{lecture.id}/quiz"

    assert (await client.get(url)).json()["questions"] == []
    assert (await client.post(url)).status_code == 401

    created = await client.post(url, headers=student.headers)

    assert created.status_code == 200

    questions = created.json()["questions"]

    # The question without enough distinct options is dropped.
    assert len(questions) == 1

    question = questions[0]

    assert sorted(question["options"]) == ["О концах", "О началах", "О серединах"]
    assert question["options"][question["answer"]] == "О началах"
    assert question["explanation"] == "Так сказано в начале."
    # Snapped to the start of a real chunk.
    assert question["start_seconds"] in {0.0, 10.0, 20.0, 30.0}
    assert "Первая мысль о началах." in fake_llm.calls[0][1][0]["content"]

    assert (await client.get(url)).json()["questions"] == questions


async def test_quiz_failures(
    client: AsyncClient,
    db: AsyncSession,
    fake_llm: FakeLLM,
    student: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(db, "Лекция", ["Мысль."])
    url = f"/api/v1/lectures/{lecture.id}/quiz"

    fake_llm.json_payload = {"questions": "не список"}
    unusable = await client.post(url, headers=student.headers)

    assert unusable.status_code == 503
    assert unusable.json()["code"] == "llm_unavailable"

    lecture.status = LectureStatus.TRANSCRIBING
    await db.commit()

    busy = await client.post(url, headers=student.headers)

    assert busy.status_code == 409
    assert busy.json()["code"] == "lecture_not_ready"

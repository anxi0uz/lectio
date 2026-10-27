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
    teacher: RegisteredUser,
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
    # Students take the quiz; the teacher makes it.
    assert (await client.post(url, headers=student.headers)).status_code == 403

    created = await client.post(url, headers=teacher.headers)

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


async def test_quiz_attempts_and_stats(
    client: AsyncClient,
    db: AsyncSession,
    teacher: RegisteredUser,
    student: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(db, "Лекция", ["Мысль о началах."])
    url = f"/api/v1/lectures/{lecture.id}/quiz"

    missing = await client.put(
        f"{url}/attempt",
        json={"answers": [0]},
        headers=student.headers,
    )

    assert missing.status_code == 409
    assert missing.json()["code"] == "quiz_missing"

    question = (await client.post(url, headers=teacher.headers)).json()["questions"][0]
    right = question["answer"]
    wrong = (right + 1) % len(question["options"])

    mismatch = await client.put(
        f"{url}/attempt",
        json={"answers": [0, 1]},
        headers=student.headers,
    )

    assert mismatch.status_code == 400
    assert mismatch.json()["code"] == "quiz_answers_mismatch"

    first = await client.put(
        f"{url}/attempt",
        json={"answers": [wrong]},
        headers=student.headers,
    )

    assert first.json()["correct"] == 0

    # A retry replaces the previous attempt.
    retry = await client.put(
        f"{url}/attempt",
        json={"answers": [right]},
        headers=student.headers,
    )

    assert retry.json() | {"updated_at": None} == {
        "answers": [right],
        "correct": 1,
        "total": 1,
        "updated_at": None,
    }

    state = await client.get(
        f"/api/v1/lectures/{lecture.id}/me",
        headers=student.headers,
    )

    assert state.json()["quiz_attempt"]["correct"] == 1

    assert (
        await client.get(f"{url}/stats", headers=student.headers)
    ).status_code == 403

    stats = (await client.get(f"{url}/stats", headers=teacher.headers)).json()

    assert stats["attempts"] == 1
    assert stats["average_share"] == 1.0
    assert stats["questions"][0]["option_counts"][right] == 1
    assert stats["questions"][0]["correct_share"] == 1.0
    assert [result["user"]["id"] for result in stats["students"]] == [student.id]

    # A new quiz drops answers to the old one.
    await client.post(url, headers=teacher.headers)
    stats = (await client.get(f"{url}/stats", headers=teacher.headers)).json()

    assert stats["attempts"] == 0
    assert stats["average_share"] is None


async def test_quiz_failures(
    client: AsyncClient,
    db: AsyncSession,
    fake_llm: FakeLLM,
    teacher: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(db, "Лекция", ["Мысль."])
    url = f"/api/v1/lectures/{lecture.id}/quiz"

    fake_llm.json_payload = {"questions": "не список"}
    unusable = await client.post(url, headers=teacher.headers)

    assert unusable.status_code == 503
    assert unusable.json()["code"] == "llm_unavailable"

    lecture.status = LectureStatus.TRANSCRIBING
    await db.commit()

    busy = await client.post(url, headers=teacher.headers)

    assert busy.status_code == 409
    assert busy.json()["code"] == "lecture_not_ready"

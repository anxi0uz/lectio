import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support import RegisteredUser, RegisterUser, create_processed_lecture

pytestmark = pytest.mark.anyio


async def test_achievements_and_leaderboard(
    client: AsyncClient,
    db: AsyncSession,
    register_user: RegisterUser,
    teacher: RegisteredUser,
    student: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(db, "Лекция", ["О началах.", "Итоги."])
    base = f"/api/v1/lectures/{lecture.id}"
    other = await register_user("other@example.com")

    assert (await client.get("/api/v1/leaderboard")).status_code == 401

    url = "/api/v1/me/achievements"
    fresh = (await client.get(url, headers=student.headers)).json()

    assert fresh["level"] == {"xp": 0, "level": 1, "level_xp": 0, "next_level_xp": 100}
    assert not any(item["unlocked"] for item in fresh["achievements"])

    question = (await client.post(f"{base}/quiz", headers=teacher.headers)).json()[
        "questions"
    ][0]

    for headers, requests in [
        (
            student.headers,
            [
                ("PUT", "progress", {"position_seconds": 20}),
                ("PUT", "quiz/attempt", {"answers": [question["answer"]]}),
                ("POST", "comments", {"text": "Понятно"}),
                ("POST", "bookmarks", {"position_seconds": 5}),
            ],
        ),
        (other.headers, [("POST", "comments", {"text": "А мне нет"})]),
    ]:
        for method, path, body in requests:
            response = await client.request(
                method,
                f"{base}/{path}",
                json=body,
                headers=headers,
            )
            assert response.status_code < 300, (path, response.text)

    mine = (await client.get(url, headers=student.headers)).json()
    unlocked = {item["id"] for item in mine["achievements"] if item["unlocked"]}
    marathon = next(item for item in mine["achievements"] if item["id"] == "marathon")

    # Started 5 + completed 50 + right answer 10 + perfect quiz 20
    # + comment 5 + bookmark 2.
    assert mine["level"]["xp"] == 92
    assert unlocked == {"first_step", "finisher", "quiz_first", "quiz_perfect"}
    assert (marathon["progress"], marathon["target"]) == (1, 5)

    # Teachers are not ranked, even with activity of their own.
    await client.post(f"{base}/comments", json={"text": "Да"}, headers=teacher.headers)

    board = (await client.get("/api/v1/leaderboard", headers=other.headers)).json()

    assert [(entry["user"]["id"], entry["level"]["xp"]) for entry in board["top"]] == [
        (student.id, 92),
        (other.id, 5),
    ]
    assert board["me"]["rank"] == 2
    assert board["top"][0]["achievements"] == 4

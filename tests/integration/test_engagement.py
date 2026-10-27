import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support import RegisteredUser, RegisterUser, create_processed_lecture

pytestmark = pytest.mark.anyio


async def test_likes_comments_and_stats(
    client: AsyncClient,
    db: AsyncSession,
    register_user: RegisterUser,
    teacher: RegisteredUser,
    student: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(db, "Лекция", ["Раз.", "Два."])
    base = f"/api/v1/lectures/{lecture.id}"
    other = await register_user("other@example.com")

    assert (await client.put(f"{base}/like")).status_code == 401

    for _ in range(2):
        liked = await client.put(f"{base}/like", headers=student.headers)
        assert liked.status_code == 204

    state = await client.get(f"{base}/me", headers=student.headers)

    assert state.json()["is_liked"] is True

    comment = await client.post(
        f"{base}/comments",
        json={"text": "  Не понял второй шаг  ", "position_seconds": 12},
        headers=student.headers,
    )

    assert comment.status_code == 201
    assert comment.json()["text"] == "Не понял второй шаг"
    assert comment.json()["author"]["id"] == student.id

    past_end = await client.post(
        f"{base}/comments",
        json={"text": "Потом", "position_seconds": 999},
        headers=student.headers,
    )

    assert past_end.status_code == 400

    await client.post(
        f"{base}/comments",
        json={"text": "Отвечу на семинаре"},
        headers=teacher.headers,
    )

    comments = (await client.get(f"{base}/comments")).json()

    assert [item["text"] for item in comments] == [
        "Отвечу на семинаре",
        "Не понял второй шаг",
    ]

    comment_url = f"{base}/comments/{comment.json()['id']}"

    await client.put(
        f"{base}/progress",
        json={"position_seconds": 20},
        headers=student.headers,
    )

    stats = (await client.get(f"{base}/stats")).json()

    assert stats | {"average_watched_share": None} == {
        "viewers": 1,
        "completed": 1,
        "average_watched_share": None,
        "likes": 1,
        "comments": 2,
        "favorites": 0,
        "bookmarks": 0,
        "quiz_attempts": 0,
        "quiz_average_share": None,
    }
    assert stats["average_watched_share"] == 1.0

    # Another student may not delete it.
    assert (await client.delete(comment_url, headers=other.headers)).status_code == 403
    # The teacher moderates the lecture's discussion.
    deleted = await client.delete(comment_url, headers=teacher.headers)
    again = await client.delete(comment_url, headers=teacher.headers)

    assert (deleted.status_code, again.status_code) == (204, 404)

    await client.delete(f"{base}/like", headers=student.headers)

    assert (await client.get(f"{base}/stats")).json()["likes"] == 0

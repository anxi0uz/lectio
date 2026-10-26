import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import Course
from tests.support import RegisteredUser, RegisterUser, create_processed_lecture

pytestmark = pytest.mark.anyio

PHRASES = [f"Фраза номер {index}." for index in range(10)]


async def _course_with_lectures(
    db: AsyncSession,
    count: int,
) -> tuple[Course, list[str]]:
    course = Course(title="Матанализ")
    db.add(course)
    await db.flush()

    lectures = [
        await create_processed_lecture(
            db,
            f"Лекция {index}",
            PHRASES,
            course_id=course.id,
        )
        for index in range(count)
    ]

    return course, [str(lecture.id) for lecture in lectures]


async def test_enrollment_and_course_progress(
    client: AsyncClient,
    db: AsyncSession,
    student: RegisteredUser,
) -> None:
    course, lecture_ids = await _course_with_lectures(db, 2)
    enrollment_url = f"/api/v1/courses/{course.id}/enrollment"

    details = await client.get(f"/api/v1/courses/{course.id}")

    assert details.json()["lectures_count"] == 2
    assert details.json()["total_duration_seconds"] == 200.0

    first = await client.put(enrollment_url, headers=student.headers)
    again = await client.put(enrollment_url, headers=student.headers)
    await client.put(
        f"/api/v1/lectures/{lecture_ids[0]}/progress",
        headers=student.headers,
        json={"position_seconds": 95},
    )

    courses = (await client.get("/api/v1/me/courses", headers=student.headers)).json()

    assert first.status_code == again.status_code == 204
    assert [item["id"] for item in courses] == [str(course.id)]
    assert courses[0]["completed_lectures"] == 1
    assert courses[0]["progress"] == 0.5

    await client.delete(enrollment_url, headers=student.headers)

    assert (
        await client.get("/api/v1/me/courses", headers=student.headers)
    ).json() == []


async def test_watch_progress(
    client: AsyncClient,
    db: AsyncSession,
    student: RegisteredUser,
) -> None:
    lecture = await create_processed_lecture(db, "Лекция", PHRASES)
    url = f"/api/v1/lectures/{lecture.id}/progress"

    initial = await client.get(url, headers=student.headers)
    halfway = await client.put(
        url,
        headers=student.headers,
        json={"position_seconds": 40},
    )
    continue_watching = await client.get(
        "/api/v1/me/continue-watching",
        headers=student.headers,
    )
    beyond_end = await client.put(
        url,
        headers=student.headers,
        json={"position_seconds": 500},
    )
    rewound = await client.put(
        url,
        headers=student.headers,
        json={"position_seconds": 10},
    )
    reset = await client.put(
        url,
        headers=student.headers,
        json={"position_seconds": 10, "completed": False},
    )
    negative = await client.put(
        url,
        headers=student.headers,
        json={"position_seconds": -1},
    )

    assert initial.json()["position_seconds"] == 0
    assert initial.json()["completed"] is False
    assert halfway.json()["completed"] is False
    assert [item["lecture"]["id"] for item in continue_watching.json()] == [
        str(lecture.id),
    ]
    assert beyond_end.json()["position_seconds"] == 100
    assert beyond_end.json()["completed"] is True
    assert rewound.json()["completed"] is True
    assert reset.json()["completed"] is False
    assert negative.status_code == 422


async def test_favorites_and_bookmarks(
    client: AsyncClient,
    db: AsyncSession,
    register_user: RegisterUser,
    student: RegisteredUser,
) -> None:
    other = await register_user("other-student@example.com")
    lecture = await create_processed_lecture(db, "Интегралы", PHRASES)
    lecture_url = f"/api/v1/lectures/{lecture.id}"

    await client.put(f"{lecture_url}/favorite", headers=student.headers)
    await client.put(f"{lecture_url}/favorite", headers=student.headers)
    favorites = await client.get("/api/v1/me/favorites", headers=student.headers)

    assert [item["id"] for item in favorites.json()] == [str(lecture.id)]

    late = await client.post(
        f"{lecture_url}/bookmarks",
        headers=student.headers,
        json={"position_seconds": 75, "note": "  Формула Ньютона–Лейбница  "},
    )
    early = await client.post(
        f"{lecture_url}/bookmarks",
        headers=student.headers,
        json={"position_seconds": 12},
    )
    past_end = await client.post(
        f"{lecture_url}/bookmarks",
        headers=student.headers,
        json={"position_seconds": 101},
    )

    assert late.json()["note"] == "Формула Ньютона–Лейбница"
    assert past_end.status_code == 400

    in_lecture = await client.get(f"{lecture_url}/bookmarks", headers=student.headers)
    everywhere = await client.get("/api/v1/me/bookmarks", headers=student.headers)
    others_view = await client.get(f"{lecture_url}/bookmarks", headers=other.headers)
    foreign_edit = await client.patch(
        f"/api/v1/bookmarks/{late.json()['id']}",
        headers=other.headers,
        json={"note": "Взлом"},
    )

    assert [item["position_seconds"] for item in in_lecture.json()] == [12, 75]
    assert everywhere.json()[0]["lecture_title"] == "Интегралы"
    assert others_view.json() == []
    assert foreign_edit.status_code == 404

    edited = await client.patch(
        f"/api/v1/bookmarks/{early.json()['id']}",
        headers=student.headers,
        json={"note": "Определение"},
    )
    deleted = await client.delete(
        f"/api/v1/bookmarks/{late.json()['id']}",
        headers=student.headers,
    )

    assert edited.json()["note"] == "Определение"
    assert edited.json()["position_seconds"] == 12
    assert deleted.status_code == 204

    await client.delete(f"{lecture_url}/favorite", headers=student.headers)

    assert (
        await client.get("/api/v1/me/favorites", headers=student.headers)
    ).json() == []


async def test_dashboard_lecture_state_and_search_history(
    client: AsyncClient,
    db: AsyncSession,
    teacher: RegisteredUser,
    student: RegisteredUser,
) -> None:
    course, lecture_ids = await _course_with_lectures(db, 2)
    lecture_url = f"/api/v1/lectures/{lecture_ids[0]}"

    await client.put(
        f"/api/v1/courses/{course.id}/enrollment",
        headers=student.headers,
    )
    await client.put(f"{lecture_url}/favorite", headers=student.headers)
    await client.post(
        f"{lecture_url}/bookmarks",
        headers=student.headers,
        json={"position_seconds": 30},
    )
    await client.put(
        f"{lecture_url}/progress",
        headers=student.headers,
        json={"position_seconds": 30},
    )
    await client.put(
        f"/api/v1/lectures/{lecture_ids[1]}/progress",
        headers=student.headers,
        json={"position_seconds": 100},
    )

    for query in ("фраза", "номер", "фраза"):
        await client.get(
            "/api/v1/search",
            headers=student.headers,
            params={"q": query},
        )

    dashboard = (
        await client.get("/api/v1/me/dashboard", headers=student.headers)
    ).json()

    assert dashboard["enrolled_courses"] == 1
    assert dashboard["lectures_completed"] == 1
    assert dashboard["lectures_in_progress"] == 1
    assert dashboard["watched_seconds"] == 130
    assert dashboard["favorites"] == 1
    assert dashboard["bookmarks"] == 1
    assert dashboard["lectures_uploaded"] is None
    assert [item["lecture"]["id"] for item in dashboard["continue_watching"]] == [
        lecture_ids[0],
    ]
    assert [item["query"] for item in dashboard["recent_searches"]] == [
        "фраза",
        "номер",
    ]

    state = (await client.get(f"{lecture_url}/me", headers=student.headers)).json()
    teacher_state = (
        await client.get(f"{lecture_url}/me", headers=teacher.headers)
    ).json()

    assert state["progress"]["position_seconds"] == 30
    assert state["is_favorite"] is True
    assert state["is_enrolled_in_course"] is True
    assert state["can_manage"] is False
    assert [item["position_seconds"] for item in state["bookmarks"]] == [30]
    assert teacher_state["can_manage"] is True

    teacher_dashboard = (
        await client.get("/api/v1/me/dashboard", headers=teacher.headers)
    ).json()

    assert teacher_dashboard["lectures_uploaded"] == 0

    cleared = await client.delete(
        "/api/v1/me/search-history",
        headers=student.headers,
    )
    history = await client.get(
        "/api/v1/me/search-history",
        headers=student.headers,
    )

    assert cleared.status_code == 204
    assert history.json() == []

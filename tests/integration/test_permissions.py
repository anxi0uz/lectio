import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support import RegisteredUser, RegisterUser, create_processed_lecture

pytestmark = pytest.mark.anyio

VIDEO = ("lecture.mp4", b"\x00" * 1024, "video/mp4")


async def test_students_cannot_create_content(
    client: AsyncClient,
    student: RegisteredUser,
) -> None:
    upload = await client.post(
        "/api/v1/lectures",
        headers=student.headers,
        files={"file": VIDEO},
    )
    imported = await client.post(
        "/api/v1/lectures/import",
        headers=student.headers,
        json={"url": "https://example.com/video"},
    )
    course = await client.post(
        "/api/v1/courses",
        headers=student.headers,
        json={"title": "Мой курс"},
    )
    anonymous = await client.post(
        "/api/v1/lectures",
        files={"file": VIDEO},
    )

    assert upload.status_code == 403
    assert upload.json()["detail"] == "Only teachers can do this"
    assert imported.status_code == 403
    assert course.status_code == 403
    assert anonymous.status_code == 401


async def test_only_owner_manages_lecture_and_course(
    client: AsyncClient,
    register_user: RegisterUser,
    teacher: RegisteredUser,
    student: RegisteredUser,
) -> None:
    other_teacher = await register_user("other@example.com", role="teacher")

    course = (
        await client.post(
            "/api/v1/courses",
            headers=teacher.headers,
            json={"title": "Алгебра"},
        )
    ).json()
    lecture = (
        await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": VIDEO},
        )
    ).json()
    lecture_url = f"/api/v1/lectures/{lecture['id']}"

    assert course["owner_id"] == teacher.id
    assert lecture["owner_id"] == teacher.id

    foreign_patch = await client.patch(
        lecture_url,
        headers=other_teacher.headers,
        json={"title": "Чужая"},
    )
    student_delete = await client.delete(lecture_url, headers=student.headers)
    foreign_course = await client.post(
        "/api/v1/lectures",
        headers=other_teacher.headers,
        files={"file": VIDEO},
        data={"course_id": course["id"]},
    )
    foreign_course_delete = await client.delete(
        f"/api/v1/courses/{course['id']}",
        headers=other_teacher.headers,
    )
    own_patch = await client.patch(
        lecture_url,
        headers=teacher.headers,
        json={"course_id": course["id"]},
    )
    by_owner = await client.get(
        "/api/v1/lectures",
        params={"owner_id": teacher.id},
    )

    assert foreign_patch.status_code == 403
    assert foreign_patch.json()["detail"] == "Only the owner can change it"
    assert student_delete.status_code == 403
    assert foreign_course.status_code == 403
    assert foreign_course_delete.status_code == 403
    assert own_patch.status_code == 200
    assert [item["id"] for item in by_owner.json()] == [lecture["id"]]


async def test_content_without_owner_is_shared_by_teachers(
    client: AsyncClient,
    db: AsyncSession,
    teacher: RegisteredUser,
    student: RegisteredUser,
) -> None:
    seeded = await create_processed_lecture(db, "Из CLI", ["Текст."])
    url = f"/api/v1/lectures/{seeded.id}"

    by_student = await client.patch(
        url,
        headers=student.headers,
        json={"title": "Нет"},
    )
    by_teacher = await client.patch(
        url,
        headers=teacher.headers,
        json={"title": "Да"},
    )

    assert by_student.status_code == 403
    assert by_teacher.json()["title"] == "Да"


async def test_reading_stays_public(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    lecture = await create_processed_lecture(db, "Открытая", ["Публичный текст."])

    responses = [
        await client.get("/api/v1/lectures"),
        await client.get(f"/api/v1/lectures/{lecture.id}"),
        await client.get(f"/api/v1/lectures/{lecture.id}/segments"),
        await client.get(f"/api/v1/lectures/{lecture.id}/subtitles.vtt"),
        await client.get(f"/api/v1/lectures/{lecture.id}/summary"),
        await client.get("/api/v1/search", params={"q": "текст"}),
        await client.get("/api/v1/courses"),
    ]

    assert [response.status_code for response in responses] == [200] * 7

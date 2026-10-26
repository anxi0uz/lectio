from uuid import UUID

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from lectio.core.jobs import JOBS_QUEUE_KEY, Job, JobKind

pytestmark = pytest.mark.anyio

VIDEO_BYTES = bytes(range(256)) * 16


async def _queued_jobs(redis: Redis) -> list[Job]:
    raw = await redis.lrange(JOBS_QUEUE_KEY, 0, -1)  # pyright: ignore[reportGeneralTypeIssues]

    return [Job.loads(item) for item in reversed(raw)]


async def test_upload_queues_processing_and_serves_video(
    client: AsyncClient,
    test_redis: Redis,
) -> None:
    response = await client.post(
        "/api/v1/lectures",
        files={"file": ("intro.mp4", VIDEO_BYTES, "video/mp4")},
        data={"title": "  Введение  "},
    )

    assert response.status_code == 202

    lecture = response.json()

    assert lecture["title"] == "Введение"
    assert lecture["status"] == "pending"
    assert lecture["source_type"] == "upload"
    assert lecture["video_url"] == f"/api/v1/lectures/{lecture['id']}/video"
    assert lecture["subtitles_url"] is None
    assert "video_path" not in lecture
    assert await _queued_jobs(test_redis) == [
        Job(JobKind.PROCESS, lecture_id=UUID(lecture["id"])),
    ]

    full = await client.get(lecture["video_url"])
    partial = await client.get(
        lecture["video_url"],
        headers={"Range": "bytes=100-199"},
    )

    assert full.status_code == 200
    assert full.headers["content-type"] == "video/mp4"
    assert full.content == VIDEO_BYTES
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 100-199/{len(VIDEO_BYTES)}"
    assert partial.content == VIDEO_BYTES[100:200]


async def test_upload_validation(
    client: AsyncClient,
) -> None:
    wrong_type = await client.post(
        "/api/v1/lectures",
        files={"file": ("notes.pdf", b"%PDF", "application/pdf")},
    )
    too_large = await client.post(
        "/api/v1/lectures",
        files={"file": ("big.mp4", b"0" * (1024 * 1024 + 1), "video/mp4")},
    )
    missing_course = await client.post(
        "/api/v1/lectures",
        files={"file": ("a.mp4", VIDEO_BYTES, "video/mp4")},
        data={"course_id": "00000000-0000-0000-0000-000000000000"},
    )
    listed = await client.get("/api/v1/lectures")

    assert wrong_type.status_code == 415
    assert too_large.status_code == 413
    assert missing_course.status_code == 404
    assert missing_course.json()["detail"] == "Course not found"
    assert listed.json() == []


async def test_import_by_url(
    client: AsyncClient,
    test_redis: Redis,
) -> None:
    response = await client.post(
        "/api/v1/lectures/import",
        json={"url": "https://www.youtube.com/watch?v=abc"},
    )
    invalid = await client.post(
        "/api/v1/lectures/import",
        json={"url": "not a url"},
    )

    assert response.status_code == 202
    assert invalid.status_code == 422

    lecture = response.json()

    assert lecture["source_type"] == "url"
    assert lecture["source_url"] == "https://www.youtube.com/watch?v=abc"
    assert lecture["video_url"] is None
    assert len(await _queued_jobs(test_redis)) == 1

    video = await client.get(f"/api/v1/lectures/{lecture['id']}/video")

    assert video.status_code == 404
    assert video.json()["detail"] == "Video file is not available yet"


async def test_lecture_crud_and_reprocess(
    client: AsyncClient,
    test_redis: Redis,
) -> None:
    course = (await client.post("/api/v1/courses", json={"title": "Геометрия"})).json()
    lecture = (
        await client.post(
            "/api/v1/lectures",
            files={"file": ("one.webm", VIDEO_BYTES, "video/webm")},
        )
    ).json()
    lecture_url = f"/api/v1/lectures/{lecture['id']}"

    assert lecture["title"] == "one"

    patched = await client.patch(
        lecture_url,
        json={"title": "Первая", "course_id": course["id"]},
    )
    by_course = await client.get(
        "/api/v1/lectures",
        params={"course_id": course["id"]},
    )
    busy = await client.post(f"{lecture_url}/reprocess")
    not_ready_segments = await client.get(f"{lecture_url}/segments")

    assert patched.status_code == 200
    assert patched.json()["title"] == "Первая"
    assert patched.json()["course_id"] == course["id"]
    assert [item["id"] for item in by_course.json()] == [lecture["id"]]
    assert busy.status_code == 409
    assert not_ready_segments.status_code == 409

    deleted = await client.delete(lecture_url)
    missing = await client.get(lecture_url)
    video = await client.get(f"{lecture_url}/video")

    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert video.status_code == 404


async def test_deleting_course_keeps_lectures(
    client: AsyncClient,
) -> None:
    course = (await client.post("/api/v1/courses", json={"title": "Физика"})).json()
    lecture = (
        await client.post(
            "/api/v1/lectures",
            files={"file": ("a.mp4", VIDEO_BYTES, "video/mp4")},
            data={"course_id": course["id"]},
        )
    ).json()

    deleted = await client.delete(f"/api/v1/courses/{course['id']}")
    after = await client.get(f"/api/v1/lectures/{lecture['id']}")

    assert deleted.status_code == 204
    assert after.json()["course_id"] is None

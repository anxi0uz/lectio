import asyncio
import time
from uuid import UUID

import pytest
from httpx import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from lectio.core.config import get_settings
from lectio.core.jobs import JOBS_QUEUE_KEY, Job, JobKind
from lectio.core.media import RemoteVideo
from lectio.db.session import get_session_factory
from lectio.modules.lectures.exceptions import DuplicateLectureError
from lectio.modules.lectures.schemas import LectureImport
from lectio.modules.lectures.service import create_imported_lecture
from tests.support import RegisteredUser, fake_url_probe, sample_media

pytestmark = pytest.mark.anyio


async def _queued_jobs(redis: Redis) -> list[Job]:
    raw = await redis.lrange(JOBS_QUEUE_KEY, 0, -1)  # pyright: ignore[reportGeneralTypeIssues]

    return [Job.loads(item) for item in reversed(raw)]


async def test_upload_queues_processing_and_serves_video(
    client: AsyncClient,
    teacher: RegisteredUser,
    test_redis: Redis,
) -> None:
    response = await client.post(
        "/api/v1/lectures",
        headers=teacher.headers,
        files={"file": ("intro.mp4", sample_media("video"), "video/mp4")},
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
    assert full.content == sample_media("video")
    assert partial.status_code == 206
    assert (
        partial.headers["content-range"]
        == f"bytes 100-199/{len(sample_media('video'))}"
    )
    assert partial.content == sample_media("video")[100:200]


async def test_upload_validation(
    client: AsyncClient,
    teacher: RegisteredUser,
) -> None:
    wrong_type = await client.post(
        "/api/v1/lectures",
        headers=teacher.headers,
        files={"file": ("notes.pdf", b"%PDF", "application/pdf")},
    )
    too_large = await client.post(
        "/api/v1/lectures",
        headers=teacher.headers,
        files={"file": ("big.mp4", b"0" * (1024 * 1024 + 1), "video/mp4")},
    )
    missing_course = await client.post(
        "/api/v1/lectures",
        headers=teacher.headers,
        files={"file": ("a.mp4", sample_media("video"), "video/mp4")},
        data={"course_id": "00000000-0000-0000-0000-000000000000"},
    )
    listed = await client.get("/api/v1/lectures")

    assert wrong_type.status_code == 415
    assert too_large.status_code == 413
    assert missing_course.status_code == 404
    assert missing_course.json()["detail"] == "Course not found"
    assert listed.json() == []


async def test_upload_checks_media_content(
    client: AsyncClient,
    teacher: RegisteredUser,
    test_redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def upload(name: str, content: bytes) -> Response:
        return await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": (name, content, "application/octet-stream")},
        )

    garbage = await upload("lecture.mp4", b"not a video at all" * 100)
    silent = await upload("silent.mp4", sample_media("silent"))
    audio = await upload("podcast.wav", sample_media("audio"))

    assert garbage.status_code == 422
    assert garbage.json()["code"] == "media_unreadable"
    assert silent.status_code == 422
    assert silent.json()["code"] == "media_no_audio"
    assert audio.status_code == 202
    assert audio.json()["duration_seconds"] == pytest.approx(2.0, abs=0.1)

    monkeypatch.setattr(get_settings(), "max_duration_hours", 1 / 3600)
    too_long = await upload("long.mp4", sample_media("video"))
    listed = await client.get("/api/v1/lectures")

    assert too_long.status_code == 422
    assert too_long.json()["code"] == "media_too_long"
    # Rejected uploads leave neither rows nor queued jobs behind.
    assert [item["title"] for item in listed.json()] == ["podcast"]
    assert len(await _queued_jobs(test_redis)) == 1


async def test_import_checks_the_page(
    client: AsyncClient,
    teacher: RegisteredUser,
) -> None:
    async def import_url(url: str) -> Response:
        return await client.post(
            "/api/v1/lectures/import",
            headers=teacher.headers,
            json={"url": url, "title": "Своё название"},
        )

    missing = await import_url("https://example.com/missing")
    live = await import_url("https://example.com/live")
    too_long = await import_url("https://example.com/long")
    named = await import_url("https://example.com/video")

    assert missing.status_code == 422
    assert missing.json()["code"] == "url_unavailable"
    assert live.json()["code"] == "url_live_stream"
    assert too_long.json()["code"] == "media_too_long"
    assert named.json()["title"] == "Своё название"


async def test_import_by_url(
    client: AsyncClient,
    teacher: RegisteredUser,
    test_redis: Redis,
) -> None:
    response = await client.post(
        "/api/v1/lectures/import",
        headers=teacher.headers,
        json={"url": "https://www.youtube.com/watch?v=abc"},
    )
    invalid = await client.post(
        "/api/v1/lectures/import",
        headers=teacher.headers,
        json={"url": "not a url"},
    )

    assert response.status_code == 202
    assert invalid.status_code == 422

    lecture = response.json()

    assert lecture["source_type"] == "url"
    assert lecture["source_url"] == "https://www.youtube.com/watch?v=abc"
    # Known before downloading: the page is checked when the lecture is created.
    assert lecture["title"] == "Видео со страницы"
    assert lecture["duration_seconds"] == 600
    assert lecture["video_url"] is None
    assert len(await _queued_jobs(test_redis)) == 1

    video = await client.get(f"/api/v1/lectures/{lecture['id']}/video")

    assert video.status_code == 404
    assert video.json()["detail"] == "Video file is not available yet"


async def test_lecture_crud_and_reprocess(
    client: AsyncClient,
    teacher: RegisteredUser,
    test_redis: Redis,
) -> None:
    course = (
        await client.post(
            "/api/v1/courses",
            headers=teacher.headers,
            json={"title": "Геометрия"},
        )
    ).json()
    lecture = (
        await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": ("one.webm", sample_media("video"), "video/webm")},
        )
    ).json()
    lecture_url = f"/api/v1/lectures/{lecture['id']}"

    assert lecture["title"] == "one"

    patched = await client.patch(
        lecture_url,
        headers=teacher.headers,
        json={"title": "Первая", "course_id": course["id"]},
    )
    by_course = await client.get(
        "/api/v1/lectures",
        params={"course_id": course["id"]},
    )
    busy = await client.post(
        f"{lecture_url}/reprocess",
        headers=teacher.headers,
    )
    not_ready_segments = await client.get(f"{lecture_url}/segments")

    assert patched.status_code == 200
    assert patched.json()["title"] == "Первая"
    assert patched.json()["course_id"] == course["id"]
    assert [item["id"] for item in by_course.json()] == [lecture["id"]]
    assert busy.status_code == 409
    assert not_ready_segments.status_code == 409

    deleted = await client.delete(lecture_url, headers=teacher.headers)
    missing = await client.get(lecture_url)
    video = await client.get(f"{lecture_url}/video")

    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert video.status_code == 404


async def test_deleting_course_keeps_lectures(
    client: AsyncClient,
    teacher: RegisteredUser,
) -> None:
    course = (
        await client.post(
            "/api/v1/courses",
            headers=teacher.headers,
            json={"title": "Физика"},
        )
    ).json()
    lecture = (
        await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": ("a.mp4", sample_media("video"), "video/mp4")},
            data={"course_id": course["id"]},
        )
    ).json()

    deleted = await client.delete(
        f"/api/v1/courses/{course['id']}",
        headers=teacher.headers,
    )
    after = await client.get(f"/api/v1/lectures/{lecture['id']}")

    assert deleted.status_code == 204
    assert after.json()["course_id"] is None


async def test_thumbnail_is_cut_from_the_video(
    client: AsyncClient,
    teacher: RegisteredUser,
) -> None:
    video = (
        await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": ("clip.mp4", sample_media("video"), "video/mp4")},
        )
    ).json()
    audio = (
        await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": ("talk.wav", sample_media("audio"), "audio/wav")},
        )
    ).json()

    first = await client.get(video["thumbnail_url"])
    again = await client.get(video["thumbnail_url"])
    audio_thumbnail = await client.get(f"/api/v1/lectures/{audio['id']}/thumbnail")

    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert first.content.startswith(b"\xff\xd8")
    assert "immutable" in first.headers["cache-control"]
    assert again.content == first.content
    assert audio["thumbnail_url"] is None
    assert audio_thumbnail.status_code == 404


async def test_repeated_video_is_offered_instead_of_reprocessed(
    client: AsyncClient,
    teacher: RegisteredUser,
    test_redis: Redis,
) -> None:
    async def upload(allow_duplicate: bool = False) -> Response:
        return await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": ("a.mp4", sample_media("video"), "video/mp4")},
            data={"allow_duplicate": str(allow_duplicate).lower()},
        )

    async def import_url(url: str, allow_duplicate: bool = False) -> Response:
        return await client.post(
            "/api/v1/lectures/import",
            headers=teacher.headers,
            json={"url": url, "allow_duplicate": allow_duplicate},
        )

    first_upload = (await upload()).json()
    same_file = await upload()
    forced_upload = await upload(allow_duplicate=True)

    assert same_file.status_code == 409
    assert same_file.json()["code"] == "lecture_duplicate"
    assert same_file.json()["lecture_id"] == first_upload["id"]
    assert forced_upload.status_code == 202

    first_import = (await import_url("https://www.youtube.com/watch?v=abc")).json()
    # Another link form of the same video.
    same_video = await import_url("https://www.youtube.com/watch?v=abc&t=60s")
    forced_import = await import_url(
        "https://www.youtube.com/watch?v=abc",
        allow_duplicate=True,
    )
    other_video = await import_url("https://www.youtube.com/watch?v=xyz")

    assert same_video.status_code == 409
    assert same_video.json()["lecture_id"] == first_import["id"]
    assert same_video.json()["title"] == "Видео со страницы"
    assert forced_import.status_code == 202
    assert other_video.status_code == 202
    # Rejected duplicates are never queued.
    assert len(await _queued_jobs(test_redis)) == 5


async def test_simultaneous_imports_of_one_video_create_one_lecture(
    test_engine: AsyncEngine,
) -> None:
    def slow_probe(url: str) -> RemoteVideo:
        # Both requests are past the page check before either reaches the
        # duplicate check, as with two teachers pressing at the same moment.
        time.sleep(0.3)
        return fake_url_probe(url)

    async def import_once() -> str:
        async with get_session_factory()() as session:
            try:
                lecture = await create_imported_lecture(
                    session,
                    None,
                    LectureImport.model_validate(
                        {"url": "https://www.youtube.com/watch?v=race"},
                    ),
                    slow_probe,
                )
            except DuplicateLectureError:
                await session.rollback()
                return "duplicate"

            await session.commit()
            return str(lecture.id)

    results = await asyncio.gather(import_once(), import_once())

    assert results.count("duplicate") == 1

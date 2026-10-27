import httpx
import pytest
from httpx import AsyncClient

from lectio.core.object_store import ObjectStore
from lectio.core.storage import (
    THUMBNAIL_FILENAME,
    fetch_media,
    lecture_dir,
    move_to_store,
    resolve_media_path,
)
from tests.support import RegisteredUser, sample_media

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def test_lecture_files_move_to_the_bucket(
    client: AsyncClient,
    object_store: ObjectStore,
    teacher: RegisteredUser,
) -> None:
    video = sample_media("video")
    lecture = (
        await client.post(
            "/api/v1/lectures",
            headers=teacher.headers,
            files={"file": ("intro.mp4", video, "video/mp4")},
        )
    ).json()
    base = f"/api/v1/lectures/{lecture['id']}"

    # While the worker processes it, the video is served from the disk.
    local = await client.get(f"{base}/video")

    assert local.status_code == 200
    assert local.content == video

    # What the worker does once processing is done.
    key = f"lectures/{lecture['id']}/video.mp4"
    await move_to_store(resolve_media_path(key))

    assert not resolve_media_path(key).exists()
    assert await object_store.size(key) == len(video)

    redirect = await client.get(f"{base}/video")

    assert redirect.status_code == 307

    async with httpx.AsyncClient() as browser:
        partial = await browser.get(
            redirect.headers["location"],
            headers={"Range": "bytes=100-199"},
        )

    # The bucket answers Range requests itself, as players need for seeking.
    assert partial.status_code == 206
    assert partial.content == video[100:200]

    # The preview is cut from the signed link and stored next to the video.
    thumbnail = await client.get(f"{base}/thumbnail")

    assert thumbnail.status_code == 307
    assert await object_store.size(f"lectures/{lecture['id']}/{THUMBNAIL_FILENAME}")

    # Reprocessing pulls the video back to the disk.
    assert await fetch_media(key) == resolve_media_path(key)
    assert resolve_media_path(key).read_bytes() == video

    deleted = await client.delete(base, headers=teacher.headers)

    assert deleted.status_code == 204
    assert await object_store.size(key) is None
    assert not lecture_dir(lecture["id"]).exists()


async def test_avatar_lives_in_the_bucket(
    client: AsyncClient,
    object_store: ObjectStore,
    teacher: RegisteredUser,
) -> None:
    user = (
        await client.put(
            "/api/v1/users/me/avatar",
            headers=teacher.headers,
            files={"file": ("photo.png", PNG, "image/png")},
        )
    ).json()
    key = f"avatars/{teacher.id}.png"

    assert not resolve_media_path(key).exists()
    assert await object_store.size(key) == len(PNG)

    redirect = await client.get(user["avatar_url"])

    assert redirect.status_code == 307

    async with httpx.AsyncClient() as browser:
        image = await browser.get(redirect.headers["location"])

    assert image.content == PNG
    assert image.headers["content-type"] == "image/png"

    await client.delete("/api/v1/users/me/avatar", headers=teacher.headers)

    assert await object_store.size(key) is None

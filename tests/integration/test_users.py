import pytest
from httpx import AsyncClient

from tests.support import RegisteredUser

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def test_profile_and_avatar(
    client: AsyncClient,
    teacher: RegisteredUser,
) -> None:
    updated = await client.patch(
        "/api/v1/users/me",
        headers=teacher.headers,
        json={"first_name": "  Мария  ", "last_name": "Кюри"},
    )
    null_name = await client.patch(
        "/api/v1/users/me",
        headers=teacher.headers,
        json={"first_name": None},
    )

    assert updated.json()["first_name"] == "Мария"
    assert null_name.status_code == 422

    fake_image = await client.put(
        "/api/v1/users/me/avatar",
        headers=teacher.headers,
        files={"file": ("photo.png", b"<svg onload=alert(1)>", "image/png")},
    )
    avatar = await client.put(
        "/api/v1/users/me/avatar",
        headers=teacher.headers,
        files={"file": ("photo.bin", PNG, "application/octet-stream")},
    )

    assert fake_image.status_code == 415
    assert avatar.status_code == 200

    avatar_url = avatar.json()["avatar_url"]
    image = await client.get(avatar_url)
    public = await client.get(f"/api/v1/users/{teacher.id}")

    assert image.headers["content-type"] == "image/png"
    assert image.content == PNG
    assert public.json() == {
        "id": teacher.id,
        "first_name": "Мария",
        "last_name": "Кюри",
        "role": "teacher",
        "avatar_url": avatar_url,
    }

    removed = await client.delete("/api/v1/users/me/avatar", headers=teacher.headers)
    after = await client.get(avatar_url)

    assert removed.status_code == 204
    assert after.status_code == 404

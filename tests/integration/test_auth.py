import pytest
from httpx import AsyncClient

from tests.support import RegisterUser

pytestmark = pytest.mark.anyio


async def test_register_login_refresh_and_logout(
    client: AsyncClient,
) -> None:
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "Anna@Example.com",
            "password": "secret-password",
            "first_name": "Анна",
            "last_name": "Иванова",
            "role": "teacher",
        },
    )

    assert registered.status_code == 201

    user = registered.json()["user"]

    assert user["email"] == "anna@example.com"
    assert user["role"] == "teacher"
    assert user["avatar_url"] is None
    assert "password_hash" not in user
    assert "refresh_token" in registered.cookies

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "anna@example.com",
            "password": "secret-password",
            "first_name": "Анна",
            "last_name": "Иванова",
        },
    )
    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "anna@example.com", "password": "wrong-password"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ANNA@example.com", "password": "secret-password"},
    )

    assert duplicate.status_code == 409
    assert wrong_password.status_code == 401
    assert login.status_code == 200

    token = login.json()["access_token"]
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me.json()["first_name"] == "Анна"

    refreshed = await client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    await client.post("/api/v1/auth/logout")
    after_logout = await client.post("/api/v1/auth/refresh")

    assert after_logout.status_code == 401


async def test_role_defaults_to_student_and_tokens_are_checked(
    client: AsyncClient,
    register_user: RegisterUser,
) -> None:
    student = await register_user("plain@example.com")

    me = await client.get("/api/v1/auth/me", headers=student.headers)
    anonymous = await client.get("/api/v1/auth/me")
    garbage = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-token"},
    )
    bad_role = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "password": "secret-password",
            "first_name": "A",
            "last_name": "B",
            "role": "admin",
        },
    )

    assert me.json()["role"] == "student"
    assert anonymous.status_code == 401
    assert garbage.status_code == 401
    assert bad_role.status_code == 422

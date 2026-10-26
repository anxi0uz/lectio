from datetime import UTC, datetime, timedelta
from functools import cache
from secrets import token_urlsafe
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from lectio.core.config import get_settings

ACCESS_TOKEN_TYPE = "access"

password_hash = PasswordHash.recommended()


@cache
def _dummy_password_hash() -> str:
    return password_hash.hash(token_urlsafe(16))


def _verify_against_dummy(password: str) -> bool:
    return password_hash.verify(password, _dummy_password_hash())


async def hash_password(password: str) -> str:
    return await run_in_threadpool(
        password_hash.hash,
        password,
    )


async def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return await run_in_threadpool(
        password_hash.verify,
        plain_password,
        hashed_password,
    )


async def burn_password_check(password: str) -> None:
    """Spend the same Argon2 time as a real check when the user is unknown.

    Without it, a fast 401 for unknown emails reveals which ones are registered.
    """
    await run_in_threadpool(
        _verify_against_dummy,
        password,
    )


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)

    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued_at,
        "exp": issued_at
        + timedelta(
            minutes=settings.access_token_expire_minutes,
        ),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> UUID:
    settings = get_settings()

    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "iat"]},
    )

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Token is not an access token")

    sub = payload["sub"]
    if not isinstance(sub, str):
        raise InvalidTokenError("Token subject is missing")

    try:
        return UUID(sub)
    except ValueError as error:
        raise InvalidTokenError(
            "Token subject is not a valid UUID",
        ) from error

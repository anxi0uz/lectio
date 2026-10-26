from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from redis.asyncio import Redis

from lectio.core.config import get_settings
from lectio.modules.auth.exceptions import InvalidRefreshTokenError


def _refresh_key(refresh_token: str) -> str:
    token_hash = sha256(
        refresh_token.encode(),
    ).hexdigest()

    return f"auth:refresh:{token_hash}"


def _user_sessions_key(user_id: UUID) -> str:
    return f"auth:user:{user_id}:sessions"


def _parse_user_id(user_id_raw: str | bytes) -> UUID:
    if isinstance(user_id_raw, bytes):
        user_id_raw = user_id_raw.decode("utf-8")

    try:
        return UUID(user_id_raw)
    except ValueError as error:
        raise InvalidRefreshTokenError from error


async def create_refresh_session(
    redis: Redis,
    user_id: UUID,
) -> str:
    refresh_token = token_urlsafe(32)
    token_key = _refresh_key(refresh_token)
    sessions_key = _user_sessions_key(user_id)
    ttl = timedelta(
        days=get_settings().refresh_token_expire_days,
    )

    # The per-user set indexes sessions so they can all be revoked at once.
    # Its TTL is bumped with every new session, so it outlives all its members.
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(token_key, str(user_id), ex=ttl)
        pipe.sadd(sessions_key, token_key)
        pipe.expire(sessions_key, ttl)
        await pipe.execute()

    return refresh_token


async def consume_refresh_session(
    redis: Redis,
    refresh_token: str,
) -> UUID:
    token_key = _refresh_key(refresh_token)
    user_id_raw = await redis.getdel(token_key)

    if user_id_raw is None:
        raise InvalidRefreshTokenError

    user_id = _parse_user_id(user_id_raw)
    await redis.srem(_user_sessions_key(user_id), token_key)

    return user_id


async def revoke_refresh_session(
    redis: Redis,
    refresh_token: str,
) -> None:
    token_key = _refresh_key(refresh_token)
    user_id_raw = await redis.getdel(token_key)

    if user_id_raw is None:
        return

    try:
        user_id = _parse_user_id(user_id_raw)
    except InvalidRefreshTokenError:
        return

    await redis.srem(_user_sessions_key(user_id), token_key)


async def revoke_all_refresh_sessions(
    redis: Redis,
    user_id: UUID,
) -> int:
    sessions_key = _user_sessions_key(user_id)
    token_keys = list(await redis.smembers(sessions_key))  # pyright: ignore[reportGeneralTypeIssues]

    if not token_keys:
        return 0

    # SREM only what was read, so a session created concurrently stays indexed.
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(*token_keys)
        pipe.srem(sessions_key, *token_keys)
        await pipe.execute()

    return len(token_keys)

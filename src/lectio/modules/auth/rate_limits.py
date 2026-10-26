from hashlib import sha256

from redis.asyncio import Redis

from lectio.core.config import get_settings
from lectio.core.rate_limit import enforce_rate_limit


def _account_key(email: str) -> str:
    # Keep raw emails out of Redis keys.
    return sha256(email.lower().encode()).hexdigest()


async def enforce_login_rate_limit(
    redis: Redis,
    client_ip: str,
    email: str,
) -> None:
    settings = get_settings()

    await enforce_rate_limit(
        redis,
        f"login:ip:{client_ip}",
        settings.login_rate_limit_per_ip,
        settings.login_rate_limit_window_seconds,
    )
    await enforce_rate_limit(
        redis,
        f"login:account:{_account_key(email)}",
        settings.login_rate_limit_per_account,
        settings.login_rate_limit_window_seconds,
    )


async def enforce_register_rate_limit(
    redis: Redis,
    client_ip: str,
) -> None:
    settings = get_settings()

    await enforce_rate_limit(
        redis,
        f"register:ip:{client_ip}",
        settings.register_rate_limit_per_ip,
        settings.register_rate_limit_window_seconds,
    )

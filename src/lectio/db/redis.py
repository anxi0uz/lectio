from functools import cache

from redis.asyncio import Redis

from lectio.core.config import get_settings


@cache
def get_redis_client() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
    )


async def get_redis() -> Redis:
    return get_redis_client()


async def close_redis() -> None:
    if get_redis_client.cache_info().currsize:
        await get_redis_client().aclose()

    get_redis_client.cache_clear()

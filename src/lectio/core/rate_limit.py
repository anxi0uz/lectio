from redis.asyncio import Redis

from lectio.core.exceptions import RateLimitExceededError


async def enforce_rate_limit(
    redis: Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Fixed-window counter: at most `limit` hits per `window_seconds`."""
    counter_key = f"ratelimit:{key}"

    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(counter_key)
        pipe.expire(counter_key, window_seconds, nx=True)
        hits, _ = await pipe.execute()

    if hits > limit:
        retry_after = await redis.ttl(counter_key)
        raise RateLimitExceededError(
            retry_after=max(retry_after, 1),
        )

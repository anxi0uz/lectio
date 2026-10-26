import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import UUID

from redis.asyncio import Redis

JOBS_QUEUE_KEY = "lectio:jobs"


class JobKind(StrEnum):
    PROCESS = "process"
    SUMMARIZE = "summarize"
    REINDEX = "reindex"


@dataclass(frozen=True, slots=True)
class Job:
    kind: JobKind
    lecture_id: UUID

    def dumps(self) -> str:
        return json.dumps(
            asdict(self),
            default=str,
        )

    @classmethod
    def loads(cls, raw: str | bytes) -> "Job":
        payload = json.loads(raw)

        return cls(
            kind=JobKind(payload["kind"]),
            lecture_id=UUID(payload["lecture_id"]),
        )


async def enqueue_job(
    redis: Redis,
    kind: JobKind,
    lecture_id: UUID,
) -> None:
    await redis.lpush(  # pyright: ignore[reportGeneralTypeIssues]
        JOBS_QUEUE_KEY,
        Job(kind, lecture_id).dumps(),
    )


async def dequeue_job(
    redis: Redis,
    # Must stay below the client's socket timeout (5 s in redis-py 8),
    # otherwise an idle BRPOP fails with a read timeout.
    timeout_seconds: int = 2,
) -> Job | None:
    item = await redis.brpop(  # pyright: ignore[reportGeneralTypeIssues]
        [JOBS_QUEUE_KEY],
        timeout=timeout_seconds,
    )

    if item is None:
        return None

    _, raw = item

    return Job.loads(raw)

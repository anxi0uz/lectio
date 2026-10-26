from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.db.redis import get_redis
from lectio.db.session import get_session
from lectio.ml.embedder import Embedder, get_query_embedder
from lectio.ml.llm import LLMClient, get_llm
from lectio.ml.reranker import Reranker, get_reranker

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session, scope="function"),
]

RedisDep = Annotated[
    Redis,
    Depends(get_redis),
]

EmbedderDep = Annotated[
    Embedder,
    Depends(get_query_embedder),
]

RerankerDep = Annotated[
    Reranker | None,
    Depends(get_reranker),
]

LLMDep = Annotated[
    LLMClient,
    Depends(get_llm),
]

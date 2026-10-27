import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lectio.api.errors import register_exception_handlers
from lectio.api.middleware import RequestLoggingMiddleware
from lectio.api.router import api_router
from lectio.core.config import get_settings
from lectio.core.logger import configure_logging
from lectio.core.object_store import get_object_store
from lectio.db.redis import close_redis
from lectio.db.session import dispose_engine
from lectio.ml.embedder import get_query_embedder
from lectio.ml.llm import close_llm
from lectio.ml.reranker import get_reranker

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncGenerator[None]:
    if store := get_object_store():
        await store.ensure_bucket()

    if get_settings().preload_models:
        await asyncio.to_thread(get_query_embedder)
        await asyncio.to_thread(get_reranker)

    log.info("application_started")

    yield

    log.info("application_stopping")

    await close_llm()
    await close_redis()
    await dispose_engine()

    log.info("application_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(settings.debug)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "Content-Range",
            "Accept-Ranges",
        ],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

from collections.abc import AsyncGenerator
from functools import cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lectio.core.config import get_settings


@cache
def get_engine() -> AsyncEngine:
    settings = get_settings()

    return create_async_engine(
        settings.database_url,
        echo=settings.sql_echo,
        hide_parameters=True,
        pool_pre_ping=True,
    )


@cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Unit of work for one request: commit on success, rollback on error.

    Services only flush; the transaction boundary lives here.
    """
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

        await session.commit()


async def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()

    get_session_factory.cache_clear()
    get_engine.cache_clear()

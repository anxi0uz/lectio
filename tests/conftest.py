import os
import tempfile

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://lectio:lectio@127.0.0.1:5433/lectio_test",
)

TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    "redis://127.0.0.1:6380/0",
)

# Settings are read lazily, so pinning the environment before the app is
# imported is enough. Assigned unconditionally, not setdefault: an exported
# DATABASE_URL pointing at a dev database must never be truncated by tests.
os.environ.update(
    {
        "DATABASE_URL": TEST_DATABASE_URL,
        "REDIS_URL": TEST_REDIS_URL,
        "STORAGE_DIR": tempfile.mkdtemp(prefix="lectio-test-"),
        "JWT_SECRET": "test-jwt-secret-that-is-at-least-32-characters",
        "REFRESH_COOKIE_SECURE": "false",
        "MAX_UPLOAD_MB": "1",
        "PRELOAD_MODELS": "false",
        "RERANKER_MODEL": "",
        "DEBUG": "false",
        "SQL_ECHO": "false",
    }
)

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession  # noqa: E402

import lectio.models  # noqa: E402, F401
from lectio.db.base import Base  # noqa: E402
from lectio.db.redis import close_redis, get_redis_client  # noqa: E402
from lectio.db.session import (  # noqa: E402
    dispose_engine,
    get_engine,
    get_session_factory,
)
from lectio.main import app  # noqa: E402
from lectio.ml.embedder import get_query_embedder  # noqa: E402
from lectio.ml.llm import get_llm  # noqa: E402
from lectio.modules.lectures.router import get_url_probe  # noqa: E402
from tests.support import (  # noqa: E402
    FakeEmbedder,
    FakeLLM,
    RegisteredUser,
    RegisterUser,
    alembic_config,
    fake_url_probe,
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def migrated_database() -> None:
    """Build the schema once per run from migrations, not from the models."""
    engine = create_engine(TEST_DATABASE_URL)

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    engine.dispose()

    command.upgrade(alembic_config(), "head")


@pytest.fixture
async def test_engine(
    migrated_database: None,
) -> AsyncGenerator[AsyncEngine]:
    engine = get_engine()
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)

    async with engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"),
        )

    try:
        yield engine
    finally:
        # The engine is cached per process but its pool is bound to the
        # event loop, and every test gets a new loop.
        await dispose_engine()


@pytest.fixture
async def test_redis() -> AsyncGenerator[Redis]:
    redis = get_redis_client()

    await redis.flushdb()

    try:
        yield redis
    finally:
        await redis.flushdb()
        await close_redis()


@pytest.fixture
async def db(
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
async def client(
    test_engine: AsyncEngine,
    test_redis: Redis,
    fake_llm: FakeLLM,
) -> AsyncGenerator[AsyncClient]:
    app.dependency_overrides[get_query_embedder] = FakeEmbedder
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_url_probe] = lambda: fake_url_probe

    transport = ASGITransport(
        app=app,
        raise_app_exceptions=True,
    )

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def register_user(
    client: AsyncClient,
) -> RegisterUser:
    async def register_user_impl(
        email: str,
        role: str = "student",
        password: str = "test-password",
        first_name: str = "Test",
        last_name: str = "User",
    ) -> RegisteredUser:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
            },
        )
        assert response.status_code == 201

        payload = response.json()

        return RegisteredUser(
            id=payload["user"]["id"],
            email=payload["user"]["email"],
            access_token=payload["access_token"],
        )

    return register_user_impl


@pytest.fixture
async def teacher(
    register_user: RegisterUser,
) -> RegisteredUser:
    return await register_user("teacher@example.com", role="teacher")


@pytest.fixture
async def student(
    register_user: RegisterUser,
) -> RegisteredUser:
    return await register_user("student@example.com")

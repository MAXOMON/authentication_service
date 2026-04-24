import asyncio
import os

import asyncpg
import pytest
import pytest_asyncio
import redis.asyncio as redis
from asgi_lifespan import LifespanManager
from fastapi_limiter import FastAPILimiter
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


POSTGRES_IP_ADDRESS = "localhost"
PSQL_TEST_PORT = 5433
PSQL_TEST_USERNAME = "test_user"
PSQL_TEST_PASSWORD = "test_password"
PSQL_TEST_DB_NAME = "auth_test"
PSQL_TEST_DB_URL = f"postgresql+asyncpg://{PSQL_TEST_USERNAME}:{PSQL_TEST_PASSWORD}@{POSTGRES_IP_ADDRESS}:{PSQL_TEST_PORT}/{PSQL_TEST_DB_NAME}"

REDIS_TEST_PORT = 7000
REDIS_TEST_URL = f"redis://localhost:{REDIS_TEST_PORT}/0"

os.environ["DATABASE_URL"] = PSQL_TEST_DB_URL
os.environ["POSTGRES_USER"] = PSQL_TEST_USERNAME
os.environ["POSTGRES_PASSWORD"] = PSQL_TEST_PASSWORD
os.environ["POSTGRES_PORT"] = str(PSQL_TEST_PORT)
os.environ["POSTGRES_DB"] = PSQL_TEST_DB_NAME
os.environ["POSTGRES_IP_ADDRESS"] = POSTGRES_IP_ADDRESS
os.environ["REDIS_PORT"] = str(REDIS_TEST_PORT)
os.environ["REDIS_URL"] = REDIS_TEST_URL

from app.models.pydantic import JWTokenModel, RefreshTokenModel, UserFullModel

JWTokenModel.model_config.update({"arbitrary_types_allowed": True})
RefreshTokenModel.model_config.update({"arbitrary_types_allowed": True})
UserFullModel.model_config.update({"arbitrary_types_allowed": True})


from app.config import settings
from app.database import get_session
from app.main import app
from app.models.db_tables import Base


pytest_plugins = [
    "tests.fixtures.users",
    "tests.fixtures.tokens",
]


@pytest_asyncio.fixture(scope="session")
async def docker_postgres():
    """Запусти POSTGRES в docker и проверь готовность!"""
    container_name = "test_postgresql_temp"
    process_start = await asyncio.create_subprocess_exec(
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-e",
        f"POSTGRES_USER={PSQL_TEST_USERNAME}",
        "-e",
        f"POSTGRES_PASSWORD={PSQL_TEST_PASSWORD}",
        "-e",
        f"POSTGRES_DB={PSQL_TEST_DB_NAME}",
        "-p",
        f"{PSQL_TEST_PORT}:5432",
        "--rm",
        "postgres:15",
    )
    await process_start.wait()

    # проверка готовности
    for _ in range(30):
        try:
            connection = await asyncpg.connect(
                user=PSQL_TEST_USERNAME,
                password=PSQL_TEST_PASSWORD,
                database=PSQL_TEST_DB_NAME,
                host="localhost",
                port=PSQL_TEST_PORT,
            )
            await connection.close()
            break
        except Exception:
            await asyncio.sleep(1)
    else:
        raise RuntimeError("PostgreSQL не запустился")

    yield

    process_stop = await asyncio.create_subprocess_exec(
        "docker", "stop", container_name
    )
    await process_stop.wait()


@pytest_asyncio.fixture(scope="session")
async def docker_redis():
    """Запусти Redis в docker и проверь готовность!"""
    container_name = "test_redis_temp"
    process_start = await asyncio.create_subprocess_exec(
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-p",
        f"{REDIS_TEST_PORT}:6379",
        "--rm",
        "redis:7-alpine",
    )
    await process_start.wait()

    # проверка готовности

    for _ in range(30):
        try:
            client = redis.from_url(REDIS_TEST_URL)
            await client.ping()
            await client.aclose()
            break
        except Exception:
            await asyncio.sleep(1)
    else:
        raise RuntimeError("Redis не запустился")

    yield

    process_stop = await asyncio.create_subprocess_exec(
        "docker", "stop", container_name
    )

    await process_stop.wait()


# @pytest.fixture(scope="session")
# def event_loop():
#     """Создай цикл событий для всей сессии тестов"""
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine(docker_postgres):
    """Создай движок для test_db и примени миграции Alembic"""
    import subprocess

    env = os.environ.copy()
    subprocess.run(["alembic", "upgrade", "head"], env=env, check=True)

    engine = create_async_engine(PSQL_TEST_DB_URL, echo=True)
    yield engine
    await engine.dispose()
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.drop_all)
    #     await conn.run_sync(Base.metadata.create_all)
    # yield engine
    # await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def session(test_engine):
    """Для изолированной транзакции в каждом тесте"""
    async_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    engine = create_async_engine(PSQL_TEST_DB_URL)
    async with engine.begin() as conn:
        tables = Base.metadata.sorted_tables
        for table in tables:
            await conn.execute(
                text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE;")
            )

        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def override_get_session(session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
# @pytest_asyncio.fixture
async def clear_redis():
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.flushall()
    await redis_client.aclose()
    # yield


@pytest_asyncio.fixture(scope="session")
async def app_with_redis(docker_redis):
    return app


@pytest_asyncio.fixture(scope="session")
async def async_client(app_with_redis):
    async with LifespanManager(app_with_redis) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

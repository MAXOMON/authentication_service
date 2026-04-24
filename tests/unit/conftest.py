import pytest_asyncio


@pytest_asyncio.fixture(scope="session")
async def docker_postgres():
    yield

@pytest_asyncio.fixture(scope="session")
async def docker_redis():
    yield

@pytest_asyncio.fixture(scope="session")
async def test_engine(docker_postgres):
    yield

@pytest_asyncio.fixture(scope="function")
async def session(test_engine):
    yield

@pytest_asyncio.fixture(autouse=False)
async def clean_tables():
    yield

@pytest_asyncio.fixture(autouse=False)
async def override_get_session(session):
    yield

@pytest_asyncio.fixture(autouse=False)
async def clear_redis():
    yield


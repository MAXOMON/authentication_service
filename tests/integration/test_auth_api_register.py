from base64 import b64encode

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import User
from tests.fixtures.constants import USER_EMAIL, USER_PASSWORD
from tests.fixtures.users import create_user


URL = "/auth/register"

CREDENTIALS_ERROR_CASES = [
    {
        "id": "email_error",
        "credentials": f":{USER_PASSWORD}",
    },
    {
        "id": "password_error",
        "credentials": f"{USER_EMAIL}:",
    },
    {
        "id": "empty_fields",
        "credentials": ":",
    },
]


@pytest.mark.asyncio
async def test_success(async_client: AsyncClient, session: AsyncSession) -> None:
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 201
    assert response.json()["message"] == "Register successful"
    user = await session.scalar(select(User).where(User.email == USER_EMAIL))
    assert user is not None


@pytest.mark.asyncio
async def test_exists_user_error(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"
    user = await session.scalar(select(User).where(User.email == USER_EMAIL))
    assert user is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CREDENTIALS_ERROR_CASES, ids=lambda c: c["id"])
async def test_credentials_errors(async_client: AsyncClient, case) -> None:
    credentials = case["credentials"]
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Credentials"
    headers = response.headers.items()
    assert ("www-authenticate", "Basic") in headers


@pytest.mark.asyncio
async def test_rate_limiter(
    async_client: AsyncClient,
) -> None:
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    for _ in range(settings.RATE_LIMIT_REGISTER):
        response = await async_client.post(
            url=URL, headers={"Authorization": f"Basic {encoded}"}
        )
        assert response.status_code in (201, 409)

    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

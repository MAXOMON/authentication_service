from base64 import b64encode

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import RefreshToken, User
from app.models.pydantic import JWTokenModel
from tests.fixtures.constants import DEVICE_ID, USER_EMAIL, USER_PASSWORD
from tests.fixtures.tokens import create_token_model, add_refresh_token_to_db
from tests.fixtures.users import create_user


URL = "/auth/login"

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
async def test_success(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"

    device_id = response.cookies.get("device_id")
    refresh_token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.id == user.id, RefreshToken.device_id == device_id
        )
    )
    assert refresh_token is not None


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


@pytest.mark.asyncio
async def test_fake_user_error(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    email = "nonexistent@example.com"
    credentials = f"{email}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    user = await session.scalar(select(User).where(User.email == email))
    assert user is None


@pytest.mark.asyncio
async def test_inactive_user_error(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session, is_active=False)
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization error"
    user = await session.scalar(select(User).where(User.email == USER_EMAIL))
    # assert user is not None and not user.is_active
    assert not (user is None or user.is_active)


@pytest.mark.asyncio
async def test_login_and_update_refresh_token(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user: User = await create_user(session)
    refresh_token: JWTokenModel = create_token_model(
        user_id=user.id,
        token_type="refresh"
    )
    await add_refresh_token_to_db(refresh_token, session)
    old_hash = refresh_token.token_hash
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Basic {encoded}"},
        cookies={"device_id": DEVICE_ID},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"

    result = await session.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == refresh_token.user_id,
            RefreshToken.device_id == DEVICE_ID,
        )
        .execution_options(populate_existing=True)
    )
    new_refresh_token = result.scalar_one_or_none()
    assert new_refresh_token is not None

    assert response.cookies.get("refresh_token") == new_refresh_token.token_hash
    assert old_hash != new_refresh_token.token_hash


@pytest.mark.asyncio
async def test_rate_limiter(async_client: AsyncClient, session: AsyncSession) -> None:
    inactive_user = await create_user(session, is_active=False)
    credentials = f"{USER_EMAIL}:{USER_PASSWORD}"
    encoded = b64encode(credentials.encode()).decode()
    for _ in range(settings.RATE_LIMIT_LOGIN_OR_REFRESH):
        response = await async_client.post(
            url=URL, headers={"Authorization": f"Basic {encoded}"}
        )
        assert response.status_code == 401
    response = await async_client.post(
        url=URL, headers={"Authorization": f"Basic {encoded}"}
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

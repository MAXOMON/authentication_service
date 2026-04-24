import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import User
from app.models.pydantic import JWTokenModel
from tests.fixtures.constants import DEVICE_ID
from tests.fixtures.tokens import TOKEN_ERROR_CASES, correct_access_token, create_token_model
from tests.fixtures.users import create_user


URL = "/auth/user/logout"


@pytest.mark.asyncio
async def test_success(async_client: AsyncClient, correct_access_token) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful!"
    assert response.cookies.get("access_token") != access_token.token_hash


@pytest.mark.asyncio
async def test_fake_user_error(
    async_client: AsyncClient,
) -> None:
    access_token: JWTokenModel = create_token_model(99999)
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_inactive_user_error(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session, is_active=False)
    access_token: JWTokenModel = create_token_model(user.id)
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization error"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TOKEN_ERROR_CASES, ids=lambda c: c["id"])
async def test_token_errors(
    async_client: AsyncClient,
    session: AsyncSession,
    case,
) -> None:
    user: User = await create_user(session)

    token_params: dict = case["token_params"].copy()
    token_params.setdefault("user_id", user.id)
    access_token: JWTokenModel = create_token_model(**token_params)
    device_id = DEVICE_ID if case["id"] != "another_device" else "ANOTHER_DEVICE_ID"
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == case["expected_detail"]


@pytest.mark.asyncio
async def test_rate_limiter(async_client: AsyncClient, correct_access_token) -> None:
    access_token: JWTokenModel = correct_access_token
    for _ in range(settings.RATE_LIMIT_USER_CHANGES):
        response = await async_client.post(
            url=URL,
            headers={"Authorization": f"Bearer {access_token.token_hash}"},
            cookies={"device_id": access_token.device_id},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logout successful!"
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

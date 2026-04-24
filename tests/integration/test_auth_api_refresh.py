import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import RefreshToken, User
from app.models.pydantic import JWTokenModel
from tests.fixtures.constants import DEVICE_ID
from tests.fixtures.tokens import TOKEN_ERROR_CASES, add_refresh_token_to_db, create_token_model
from tests.fixtures.users import create_user


URL = "auth/refresh"


@pytest.mark.asyncio
async def test_success(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    old_refresh_token: JWTokenModel = create_token_model(user.id, "refresh")
    await add_refresh_token_to_db(old_refresh_token, session)
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {old_refresh_token.token_hash}"},
        cookies={"device_id": old_refresh_token.device_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Refreshing successful!"
    assert old_refresh_token.token_hash != response.cookies.get("refresh_token")
    assert response.cookies.get("access_token") is not None
    result = await session.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.device_id == old_refresh_token.device_id,
        )
        .execution_options(populate_existing=True)
    )
    new_refresh_token = result.scalar_one_or_none()
    assert new_refresh_token is not None
    assert old_refresh_token.token_hash != new_refresh_token.token_hash


@pytest.mark.asyncio
async def test_fake_user_error(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    refresh_token: JWTokenModel = create_token_model(9999, "refresh")
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {refresh_token.token_hash}"},
        cookies={"device_id": refresh_token.device_id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

    fake_user = await session.scalar(
        select(User).where(User.id == refresh_token.user_id)
    )
    assert fake_user is None


@pytest.mark.asyncio
async def test_inactive_user_error(
    async_client: AsyncClient, session: AsyncSession
) -> None:
    user: User = await create_user(session, is_active=False)
    refresh_token: JWTokenModel = create_token_model(user.id, "refresh")
    await add_refresh_token_to_db(refresh_token, session)
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {refresh_token.token_hash}"},
        cookies={"device_id": refresh_token.device_id},
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
    token_params.setdefault(
        "user_id",
        user.id,
    )
    if case["id"] != "wrong_type":
        token_params.setdefault("token_type", "refresh")
    else:
        token_params.setdefault("token_type", "access")
    refresh_token: JWTokenModel = create_token_model(**token_params)
    if case["id"] != "wrong_type":
        await add_refresh_token_to_db(refresh_token, session)
    device_id = DEVICE_ID if case["id"] != "another_device" else "ANOTHER_DEVICE_ID"
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {refresh_token.token_hash}"},
        cookies={"device_id": device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == case["expected_detail"]


@pytest.mark.asyncio
async def test_rate_limiter(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    refresh_token: JWTokenModel = create_token_model(user.id, "refresh")
    await add_refresh_token_to_db(refresh_token, session)
    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {refresh_token.token_hash}"},
        cookies={"device_id": refresh_token.device_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Refreshing successful!"
    new_token = response.cookies.get("refresh_token")
    for _ in range(settings.RATE_LIMIT_LOGIN_OR_REFRESH - 1):
        response = await async_client.post(
            url=URL,
            headers={"Authorization": f"Bearer {new_token}"},
            cookies={"device_id": refresh_token.device_id},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Refreshing successful!"
        new_token = response.cookies.get("refresh_token")

    response = await async_client.post(
        url=URL,
        headers={"Authorization": f"Bearer {new_token}"},
        cookies={"device_id": refresh_token.device_id},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

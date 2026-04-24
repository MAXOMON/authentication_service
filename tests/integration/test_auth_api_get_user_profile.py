import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import User
from app.models.pydantic import JWTokenModel, UserFullModel
from tests.fixtures.constants import DEVICE_ID, USER_PASSWORD
from tests.fixtures.tokens import TOKEN_ERROR_CASES, correct_access_token, create_token_model
from tests.fixtures.users import create_user


URL = "/auth/user/profile"

USER_ERROR_CASES = [
    {"id": "fake_user", "user_params": {}, "expected_status_code": 404},
    {
        "id": "inactive_user",
        "user_params": {"is_active": False},
        "expected_status_code": 401,
    },
]

VALIDATION_ERROR_CASES = [
    {"id": "wrong_password_key", "json": {"": USER_PASSWORD}},
    {"id": "wrong_password_value", "json": {"password": ""}},
    {
        "id": "wrong_json",
        "json": {},
    },
]


@pytest.mark.asyncio
async def test_success(async_client: AsyncClient, correct_access_token) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.request(
        method="GET",
        url=URL,
        json={"password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 200
    assert UserFullModel(**response.json(), hashed_password="")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", USER_ERROR_CASES, ids=lambda c: c["id"])
async def test_users_error(
    async_client: AsyncClient, session: AsyncSession, case
) -> None:
    user: User = await create_user(session, **case["user_params"])
    user_id: int = user.id if case["id"] != "fake_user" else 99999
    access_token: JWTokenModel = create_token_model(user_id)
    response = await async_client.request(
        method="GET",
        url=URL,
        json={"password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == case["expected_status_code"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TOKEN_ERROR_CASES, ids=lambda c: c["id"])
async def test_token_errors(
    async_client: AsyncClient, session: AsyncSession, case
) -> None:
    user: User = await create_user(session)

    token_params: dict = case["token_params"].copy()
    token_params.setdefault("user_id", user.id)
    access_token: JWTokenModel = create_token_model(**token_params)
    device_id = DEVICE_ID if case["id"] != "another_device" else "ANOTHER_DEVICE_ID"

    response = await async_client.request(
        method="GET",
        url=URL,
        json={"password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == case["expected_detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", VALIDATION_ERROR_CASES, ids=lambda c: c["id"])
async def test_validation_errors(
    async_client: AsyncClient,
    correct_access_token,
    case,
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.request(
        method="GET",
        url=URL,
        json=case["json"],
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Validation error"


@pytest.mark.asyncio
async def test_confirmation_password_error(
    async_client: AsyncClient, correct_access_token
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.request(
        method="GET",
        url=URL,
        json={"password": "WrongPWD54321+-"},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization error"


@pytest.mark.asyncio
async def test_rate_limiter(async_client: AsyncClient, correct_access_token) -> None:
    access_token: JWTokenModel = correct_access_token
    for _ in range(settings.RATE_LIMIT_GET_USER_INFO):
        response = await async_client.request(
            method="GET",
            url=URL,
            json={"password": USER_PASSWORD},
            headers={"Authorization": f"Bearer {access_token.token_hash}"},
            cookies={"device_id": access_token.device_id},
        )
        assert response.status_code == 200
        assert UserFullModel(**response.json(), hashed_password="")

    response = await async_client.request(
        method="GET",
        url=URL,
        json={"password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

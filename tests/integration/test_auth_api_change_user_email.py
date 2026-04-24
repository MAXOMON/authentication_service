import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import User
from app.models.pydantic import JWTokenModel
from tests.fixtures.constants import DEVICE_ID, USER_PASSWORD
from tests.fixtures.tokens import TOKEN_ERROR_CASES, correct_access_token, create_token_model
from tests.fixtures.users import create_user


URL = "/auth/user/change_email"
NEW_EMAIL = "new_email@example.com"

VALIDATION_ERROR_CASES = [
    {"id": "wrong_email_key", "json": {"": NEW_EMAIL, "password": USER_PASSWORD}},
    {"id": "wrong_password_key", "json": {"email": NEW_EMAIL, "": USER_PASSWORD}},
    {"id": "wrong_keys", "json": {"": NEW_EMAIL, "": USER_PASSWORD}},
    {"id": "wrong_email_value", "json": {"email": "", "password": USER_PASSWORD}},
    {"id": "wrong_password_value", "json": {"email": NEW_EMAIL, "password": ""}},
    {"id": "wrong_values", "json": {"email": "", "password": ""}},
    {
        "id": "wrong_json",
        "json": {},
    },
]


@pytest.mark.asyncio
async def test_success(
    async_client: AsyncClient,
    session: AsyncSession,
    correct_access_token,
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.post(
        url=URL,
        json={"email": NEW_EMAIL, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Email changed successful"
    user = await session.scalar(select(User).where(User.email == NEW_EMAIL))
    assert user is not None

    second_response = await async_client.post(
        url=URL,
        json={"email": "new" + NEW_EMAIL, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert second_response.status_code == 401
    assert second_response.json()["detail"] == "Invalid Token"


@pytest.mark.asyncio
async def test_inactive_user_error(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session, is_active=False)
    access_token: JWTokenModel = create_token_model(user.id)
    response = await async_client.post(
        url=URL,
        json={
            "email": NEW_EMAIL,
            "password": USER_PASSWORD,
        },
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization error"


@pytest.mark.asyncio
async def test_fake_user_error(
    async_client: AsyncClient,
) -> None:
    access_token: JWTokenModel = create_token_model(99999)
    response = await async_client.post(
        url=URL,
        json={
            "email": NEW_EMAIL,
            "password": USER_PASSWORD,
        },
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


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
    device_id = DEVICE_ID
    if case["id"] == "another_device":
        device_id = "ANOTHER_DEVICE_ID"

    response = await async_client.post(
        url=URL,
        json={
            "email": NEW_EMAIL,
            "password": USER_PASSWORD,
        },
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == case["expected_detail"]


@pytest.mark.asyncio
async def test_email_conflict(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    access_token: JWTokenModel = create_token_model(user.id)
    second_user: User = await create_user(session, NEW_EMAIL)
    response = await async_client.post(
        url=URL,
        json={
            "email": second_user.email,
            "password": USER_PASSWORD,
        },
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"

    user = await session.get(User, user.id)
    assert user.email != second_user.email


@pytest.mark.asyncio
@pytest.mark.parametrize("case", VALIDATION_ERROR_CASES, ids=lambda c: c["id"])
async def test_validation_errors(
    async_client: AsyncClient, correct_access_token, case
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.post(
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
    response = await async_client.post(
        url=URL,
        json={
            "email": NEW_EMAIL,
            "password": "WrongPWD54321+-",
        },
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization error"


@pytest.mark.asyncio
async def test_rate_limiter(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    access_token: JWTokenModel = create_token_model(user.id)
    for i in range(settings.RATE_LIMIT_USER_CHANGES):
        response = await async_client.post(
            url=URL,
            json={"email": str(i) + NEW_EMAIL, "password": USER_PASSWORD},
            headers={"Authorization": f"Bearer {access_token.token_hash}"},
            cookies={"device_id": access_token.device_id},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Email changed successful"
        access_token: JWTokenModel = create_token_model(user.id, version=user.version)

    response = await async_client.post(
        url=URL,
        json={"email": "finish" + NEW_EMAIL, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

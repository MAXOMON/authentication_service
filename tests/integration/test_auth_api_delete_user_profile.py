import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import User
from app.models.pydantic import JWTokenModel
from tests.fixtures.constants import DEVICE_ID, USER_EMAIL, USER_PASSWORD
from tests.fixtures.tokens import TOKEN_ERROR_CASES, correct_access_token, create_token_model
from tests.fixtures.users import create_user


URL = "/auth/user/profile"

VALIDATION_ERROR_CASES = [
    {
        "id": "wrong_email_key",
        "json": {
            "": USER_EMAIL,
            "password": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_password_key",
        "json": {
            "email": USER_EMAIL,
            "": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_keys",
        "json": {
            "": USER_EMAIL,
            "": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_email_value",
        "json": {
            "email": "",
            "password": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_password_value",
        "json": {
            "email": USER_EMAIL,
            "password": "",
        },
    },
    {
        "id": "wrong_values",
        "json": {
            "email": "",
            "password": "",
        },
    },
    {
        "id": "wrong_json",
        "json": {},
    },
]

CONFIRMATION_ERROR_CASES = [
    {
        "id": "wrong_email",
        "json": {"email": "Wrong@email.com", "password": USER_PASSWORD},
        "expected_status_code": 409,
    },
    {
        "id": "wrong_password",
        "json": {"email": USER_EMAIL, "password": "WrongPassword54321+-"},
        "expected_status_code": 401,
    },
    {
        "id": "wrong_credentials",
        "json": {"email": "Wrong@email.com", "password": "WrongPassword54321+-"},
        "expected_status_code": 401,
    },
]


@pytest.mark.asyncio
async def test_success(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    access_token: JWTokenModel = create_token_model(user.id)

    response = await async_client.request(
        method="DELETE",
        url=URL,
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Soft-deleting successful"
    await session.refresh(user)
    assert user.is_active == False
    assert user.version != access_token.version
    assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_fake_user_error(
    async_client: AsyncClient,
) -> None:
    access_token: JWTokenModel = create_token_model(99999)
    response = await async_client.request(
        method="DELETE",
        url=URL,
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
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

    response = await async_client.request(
        method="DELETE",
        url=URL,
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
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
    device_id = DEVICE_ID
    if case["id"] == "another_device":
        device_id = "ANOTHER_DEVICE_ID"

    response = await async_client.request(
        method="DELETE",
        url=URL,
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == case["expected_detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", VALIDATION_ERROR_CASES, ids=lambda c: c["id"])
async def test_validation_errors(
    async_client: AsyncClient, correct_access_token, case
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.request(
        method="DELETE",
        url=URL,
        json=case["json"],
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Validation error"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CONFIRMATION_ERROR_CASES, ids=lambda c: c["id"])
async def test_confirmation_error(
    async_client: AsyncClient, correct_access_token, case
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.request(
        method="DELETE",
        url=URL,
        json=case["json"],
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == case["expected_status_code"]


@pytest.mark.asyncio
async def test_rate_limiter(
    async_client: AsyncClient,
    session: AsyncSession,
) -> None:
    user: User = await create_user(session)
    access_token: JWTokenModel = create_token_model(user.id)
    for _ in range(settings.RATE_LIMIT_USER_CHANGES):
        response = await async_client.request(
            method="DELETE",
            url=URL,
            json={"email": USER_EMAIL, "password": USER_PASSWORD},
            headers={"Authorization": f"Bearer {access_token.token_hash}"},
            cookies={"device_id": access_token.device_id},
        )
        assert response.status_code in (200, 401)

    await session.refresh(user)
    assert user.is_active == False
    response = await async_client.request(
        method="DELETE",
        url=URL,
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

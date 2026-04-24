import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_tables import User
from app.models.pydantic import JWTokenModel
from tests.fixtures.constants import DEVICE_ID, USER_PASSWORD
from tests.fixtures.tokens import TOKEN_ERROR_CASES, correct_access_token, create_token_model
from tests.fixtures.users import create_user


URL = "/auth/user/change_password"
NEW_PASSWORD = USER_PASSWORD + USER_PASSWORD


VALIDATION_ERROR_CASES = [
    {
        "id": "wrong_new_password_key",
        "json": {
            "": NEW_PASSWORD,
            "password": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_password_key",
        "json": {
            "new_password": NEW_PASSWORD,
            "": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_keys",
        "json": {
            "": NEW_PASSWORD,
            "": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_new_password_value",
        "json": {
            "new_password": "",
            "password": USER_PASSWORD,
        },
    },
    {
        "id": "wrong_password_value",
        "json": {"new_password": NEW_PASSWORD, "password": ""},
    },
    {
        "id": "wrong_values",
        "json": {
            "new_password": "",
            "password": "",
        },
    },
    {
        "id": "wrong_json",
        "json": {},
    },
]


@pytest.mark.asyncio
async def test_success(
    async_client: AsyncClient, session: AsyncSession, correct_access_token
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.post(
        url=URL,
        json={"new_password": NEW_PASSWORD, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successful"
    user: User = await session.get(User, access_token.user_id)
    assert user.version != access_token.version


@pytest.mark.asyncio
async def test_fake_user_error(
    async_client: AsyncClient,
) -> None:
    access_token: JWTokenModel = create_token_model(99999)
    response = await async_client.post(
        url=URL,
        json={"new_password": NEW_PASSWORD, "password": USER_PASSWORD},
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
        json={"new_password": NEW_PASSWORD, "password": USER_PASSWORD},
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

    response = await async_client.post(
        url=URL,
        json={"new_password": NEW_PASSWORD, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": device_id},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == case["expected_detail"]


@pytest.mark.asyncio
async def test_passwords_conflict(
    async_client: AsyncClient, correct_access_token
) -> None:
    access_token: JWTokenModel = correct_access_token
    response = await async_client.post(
        url=URL,
        json={"new_password": USER_PASSWORD, "password": USER_PASSWORD},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Passwords must be different!"


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
        json={"new_password": NEW_PASSWORD, "password": "WrongPWD54321+-"},
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
    password = USER_PASSWORD
    new_password = "1" + password
    user_version = user.version
    for _ in range(settings.RATE_LIMIT_USER_CHANGES):
        response = await async_client.post(
            url=URL,
            json={
                "new_password": new_password,
                "password": password,
            },
            headers={"Authorization": f"Bearer {access_token.token_hash}"},
            cookies={"device_id": access_token.device_id},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successful"
        password = new_password
        new_password = "1" + password
        user_version += 1
        access_token = create_token_model(user.id, version=user_version)

    response = await async_client.post(
        url=URL,
        json={"new_password": new_password, "password": password},
        headers={"Authorization": f"Bearer {access_token.token_hash}"},
        cookies={"device_id": access_token.device_id},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

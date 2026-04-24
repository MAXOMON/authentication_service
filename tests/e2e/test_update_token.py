from datetime import timedelta
from uuid import uuid4
from freezegun import freeze_time
import pytest
from httpx import AsyncClient

from app.config import settings

from tests.fixtures.user_session import UserSession





@pytest.mark.asyncio
async def test_update_tokens(
    async_client: AsyncClient
) -> None:
    """
    ...
    """
    # initialization
    user_email = f"user{uuid4()}@example.com"
    user_password = "Secure123!"
    device_id = str(uuid4())

    session = UserSession(async_client)
    session.user_init(
        username=user_email,
        password=user_password,
        device_id=device_id
    )
    with freeze_time("2026-01-01 12:00:00") as frozen_time:
        # registration
        await session.register()
        # login
        await session.login()
        # get_profile
        get_profile_response = await session.get_profile()
        assert get_profile_response.status_code == 200
        # move to time when access token was expired
        frozen_time.tick(timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES))
        # failed get_profile
        get_profile_response = await session.get_profile()
        assert get_profile_response.status_code == 401
        # refresh
        await session.refresh()
        # move to time when refresh token was expired
        frozen_time.tick(timedelta(minutes=settings.REFRESH_TOKEN_EXPIRES_MINUTES))
        # failed refresh
        failed_refresh_response = await session.refresh()
        assert failed_refresh_response.status_code == 401
        # login
        await session.login()
        # get profile
        get_profile_response = await session.get_profile()
        assert get_profile_response.status_code == 200
        # delete profile
        delete_profile_response = await session.delete_profile()
        assert delete_profile_response.status_code == 200
        # failed get profile
        failed_get_profile_response = await session.get_profile()
        assert failed_get_profile_response.status_code == 401


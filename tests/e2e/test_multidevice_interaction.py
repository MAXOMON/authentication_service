from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.fixtures.user_session import UserSession


@pytest.mark.asyncio
async def test_multidevice_interaction_success(
    async_client: AsyncClient
) -> None:
    """
    Пройди процедуру регистрации двух устройств.
    С мобильного телефона получи данные профиля.
    С мобильного заверши все сессии.
    С компьютера безуспешно попытайся получить данные профиля.
    С компьютера заново залогинься.
    С компьютера успешно получи данные профиля.
    """
    # initialization
    user_email = f"user{uuid4()}@example.com"
    user_password = "Secure123!"
    mobile_device_id = "mobile_Fake_id"
    pc_device_id = "pc_Fake_id"

    mobile_session = UserSession(async_client)
    mobile_session.user_init(
        username=user_email,
        password=user_password,
        device_id=mobile_device_id
    )
    pc_session = UserSession(async_client)
    pc_session.user_init(
        username=user_email,
        password=user_password,
        device_id=pc_device_id
    )
    # user registration
    await mobile_session.register()
    # mobile device login
    await mobile_session.login()
    # pc device login
    await pc_session.login()
    # mobile device get profile
    mobile_get_profile_response = await mobile_session.get_profile()
    # mobile device close all sessions
    await mobile_session.close_all_sessions()
    # falied mobile device get_profile
    failed_mobile_device_get_profile_response = await mobile_session.get_profile()
    assert failed_mobile_device_get_profile_response.status_code == 401
    # failed pc device get profile
    failed_pc_device_get_profile_response = await pc_session.get_profile()
    assert failed_pc_device_get_profile_response.status_code == 401
    # pc device second login
    await pc_session.login()
    # pc get profile
    pc_get_profile_response = await pc_session.get_profile()
    assert pc_get_profile_response.status_code == 200
    assert mobile_get_profile_response.json()["email"] == pc_get_profile_response.json()["email"]
    assert mobile_get_profile_response.json()["version"] != pc_get_profile_response.json()["version"]

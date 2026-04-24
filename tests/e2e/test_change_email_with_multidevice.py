from uuid import uuid4
import asyncio

import pytest
from httpx import AsyncClient

from tests.fixtures.user_session import UserSession



@pytest.mark.asyncio
async def test_change_email_with_multidevice_session(
    async_client: AsyncClient
) -> None:
    """
    Пройди процедуру регистрации с трёх устройств.
    Залогинься с трёх устройств.
    С мобильного телефона измени email пользователя.
        (изменится email, версия пользователя и все токены станут невалидны)
    
    """
    # initialization
    user_email = f"user{uuid4()}@example.com"
    user_password = "Secure123!"

    mobile_device_id = str(uuid4())
    tablet_device_id = str(uuid4())
    pc_device_id = str(uuid4())

    # init mobile, tablet, pc sessions
    mobile_session = UserSession(async_client)
    mobile_session.user_init(
        username=user_email,
        password=user_password,
        device_id=mobile_device_id
    )
    tablet_session = UserSession(async_client)
    tablet_session.user_init(
        username=user_email,
        password=user_password,
        device_id=tablet_device_id
    )
    pc_session = UserSession(async_client)
    pc_session.user_init(
        username=user_email,
        password=user_password,
        device_id=pc_device_id
    )
    # user registration
    await pc_session.register()
    # multidevice login
    await mobile_session.login()
    await tablet_session.login()
    await pc_session.login()
    # mobile change_email
    new_user_email = user_email + "new"
    mobile_response = await mobile_session.change_email(new_user_email)
    assert mobile_response.status_code == 200
    # tablet failed get profile
    tablet_response = await tablet_session.get_profile()
    assert tablet_response.status_code == 401
    # pc failed get profile
    pc_response = await pc_session.get_profile()
    assert pc_response.status_code == 401
    # tablet failed refresh
    tablet_response = await tablet_session.refresh()
    assert tablet_response.status_code == 401
    # pc failed refresh
    pc_response = await pc_session.refresh()
    assert pc_response.status_code == 401
    # mobile failed refresh
    mobile_response = await mobile_session.refresh()
    assert mobile_response.status_code == 401
    # pc success login with new email
    pc_session.user_email = new_user_email
    pc_response = await pc_session.login()
    assert pc_response.status_code == 200
    # mobile success login
    mobile_response = await mobile_session.login()
    assert mobile_response.status_code == 200
    # tablet success login
    tablet_session.user_email = new_user_email
    tablet_response = await tablet_session.login()
    assert tablet_response.status_code == 200
    # mobile logout
    await mobile_session.logout()
    # pc close_all_sessions
    await pc_session.close_all_sessions()
    # tablet failed get profile
    tablet_response = await tablet_session.get_profile()
    assert tablet_response.status_code == 401

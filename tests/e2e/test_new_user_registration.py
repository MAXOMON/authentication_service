from uuid import uuid4
import pytest
from httpx import AsyncClient

from tests.fixtures.user_session import UserSession


@pytest.mark.asyncio
async def test_registration_success_with_user_client(
    async_client: AsyncClient,
):  
    """
    Пройди процедуру регистрации нового пользователя.
    Залогинься. 
    Получи полные данные профиля.
    Измени пароль пользователя учётной записи.
    Безуспешно получи данные профиля, т.к. версия пользователя
        изменилась, и все выданные токены невалидны.
    Безуспешно попытайся получить новую пару токенов, через эндопинт
        'refresh'.
    Залогинься с новыми учётными данными.
    Получи данные профиля и обнаружь, что версия пользователя
        действительно изменилась.
    """
    # initialization
    user_email = f"user{uuid4()}@example.com"
    user_password = "Secure123!"
    device_id = "Fake_id"

    session = UserSession(async_client)
    session.user_init(
        username=user_email,
        password=user_password,
        device_id=device_id
    )
    # registration
    register_response = await session.register()
    # login
    login_response = await session.login()
    access_token = login_response.cookies.get("access_token")
    refresh_token = login_response.cookies.get("refresh_token")
    # get profile
    get_profile_response = await session.get_profile()
    user_version = get_profile_response.json()["version"]
    # change password
    new_user_password = user_password + "New"
    await session.change_password(new_user_password)
    # failed get profile
    failed_get_profile_response = await session.get_profile()
    assert failed_get_profile_response.status_code == 401
    # failed refresh
    failed_refresh_response = await session.refresh()
    assert failed_refresh_response.status_code == 401
    # success login with new password
    second_login_response = await session.login()
    new_access_token = second_login_response.cookies.get("access_token")
    new_refresh_token = second_login_response.cookies.get("refresh_token")
    assert not (access_token == new_access_token or refresh_token == new_refresh_token)
    # new get profile
    second_get_profile_response = await session.get_profile()
    new_user_version = second_get_profile_response.json()["version"]
    assert user_version != new_user_version

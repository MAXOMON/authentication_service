from typing import Tuple

from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.database_cruds import (
    add_or_update_refresh_token, add_user, change_user_email, change_user_password, delete_all_user_refresh_tokens,
    delete_refresh_token_by_uid_and_devid, get_full_user_information, get_refresh_token,
    get_refresh_token_by_uid_and_devid, get_user_by_email, get_user_by_id, soft_delete_user,)
from app.exceptions import (DBIsNotAvailableError, DBIsNotAvailableHTTPException, InvalidCredentialsHTTPException,
                            RefreshTokenNotFoundError, UnauthorizedHTTPException, UserNotFoundHTTPException,)
from app.models.db_tables import RefreshToken, User
from app.models.pydantic import JWTokenModel, RefreshTokenModel, UserAuth, UserFromDB, UserFullModel, UserToDB
from app.utils import _get_payload_from_token, verify_password


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login", refreshUrl="/refresh", auto_error=False
)

security = HTTPBasic()


async def add_or_update_refresh_token_to_db(
    refresh_token: JWTokenModel, session: AsyncSession
) -> None:
    """
    Добавь или обнови уже существущий рефреш-токен пользователя, выданный
        на конкретное устройство. (вспомогательная функция)

    :param refresh_token: * pydantic-модель с данными рефреш-токена
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        return await add_or_update_refresh_token(refresh_token, session)
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def add_user_to_db(user: UserToDB, session: AsyncSession) -> None:
    """
    Добавь пользователя в БД. (вспомогательная функция)

    :param user: * pydantic-модель регистрируемого пользователя
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        return await add_user(user, session)
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


def get_and_check_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> UserAuth:
    """
    Проверь на корректность введённые пользователем данные
        для доступа в систему и верни pydantic-модель пользователя.

    :param credentials: * username и password,
        введённые пользователем в BasicAuth

    :return: * Pydantic-модель, проверившая корректность введённых данных
        на внутренние требования системы

    :raises InvalidCredentialsHTTPException: данные не прошли валидацию,
        выбрось ошибку сервера 401
    """
    try:
        user = UserAuth(email=credentials.username, password=credentials.password)
        return user
    except (ValueError, AttributeError, TypeError):
        raise InvalidCredentialsHTTPException


def get_payload_from_access_token(
    token: str = Depends(oauth2_scheme),
) -> Tuple[dict, str]:
    """
    Извлеки и верни кортеж из access-токена,
        содержащий полезную нагрузку из токена + сам токен

    :param token: * исходная строка из байтов (кодированный jwtoken)

    :return: * кортеж из полезной нагрузки (payload)
        и оригинального токена (token_hash)

    :raises InvalidTokenHTTPException: * невалидный токе. 401 unauthorized
    :raises RefreshTokenExpiredHTTPException: * токен истёк. 401 unauthorized
    """
    return _get_payload_from_token(token, "access"), token


def get_payload_from_refresh_token(
    token: str = Depends(oauth2_scheme),
) -> Tuple[dict, str]:
    """
    Извлеки и верни кортеж из refresh-токена,
        содержащий полезную нагрузку из токена + сам токен

    :param token: * исходная строка из байтов (кодированный jwtoken)

    :return: * кортеж из полезной нагрузки (payload)
        и оригинального токена (token_hash)
    """
    return _get_payload_from_token(token, "refresh"), token


async def get_refresh_token_from_db(
    token_hash: str, session: AsyncSession
) -> RefreshToken | None:
    """
    Верни конкретный рефреш-токен пользователя из БД
        (вспомогательная функция)

    :param token_hash: * кодированная строка токена
    :param session: * объект сессии, для обращения к БД

    :return: * объект токена в БД

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        return await get_refresh_token(token_hash=token_hash, session=session)
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def get_refresh_token_by_uid_and_devid_from_db(
    user_id: int, device_id: str, session: AsyncSession
) -> RefreshToken | None:
    """
    Верни рефреш-токен пользователя конкретного устройства из БД.
        (вспомогательная функция)

    :param user_id: * ID-пользователя в БД
    :param device_id: * идентификатор устройства
    :param session: * объект сессии, для обращения к БД

    :return: * объект токена в БД
    """
    try:
        return await get_refresh_token_by_uid_and_devid(
            user_id=user_id, device_id=device_id, session=session
        )
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def get_user_by_email_from_db(
    user_email: str, session: AsyncSession
) -> User | None:
    """
    Верни пользователя по его email из БД. (вспомогательная функция)

    :param user_email: * строка, email пользователя
    :param session: * объект сессии, для обращения к БД

    :return: * объект пользователя из БД

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        return await get_user_by_email(user_email, session)
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def delete_all_user_refresh_tokens_from_db(
    user_id: str, session: AsyncSession
) -> None:
    """
    Удали все токены пользователя. (вспомогательная функция)

    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises UnauthorizedHTTPException: токены не были найдены в БД.
        Предположительно, попытка несанкционированного доступа в систему.
        Выбрось ошибку сервера 401
    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        return await delete_all_user_refresh_tokens(user_id=user_id, session=session)
    except RefreshTokenNotFoundError:
        raise UnauthorizedHTTPException
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


# async def delete_refresh_token_from_db(
#     refresh_token: RefreshToken, session: AsyncSession
# ) -> None:
#     """
#     Удали refresh-токен из БД. (вспомогательная функция)

#     :param refresh_token: * Объект refresh-токена, хранимый в БД
#     :param session: * объект сессии, для обращения к БД

#     :return: ``None``

#     :raises UnauthorizedHTTPException: токен не был найден в БД.
#         Предположительно, попытка несанкционированного доступа в систему.
#         Выбрось ошибку сервера 401
#     :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
#         выбрось ошибку сервера 500
#     """
#     try:
#         return await delete_refresh_token(refresh_token, session)
#     except RefreshTokenNotFoundError:
#         raise UnauthorizedHTTPException
#     except DBIsNotAvailableError:
#         raise DBIsNotAvailableHTTPException


async def get_full_user_information_from_db(
    user_id: int, session: AsyncSession
) -> UserFullModel:
    """
    Верни полную информацию о пользователе из БД. (вспомогательная функция)

    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * pydantic-модель со связанными данными о пользователе

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        user: User = await get_full_user_information(
            user_id=user_id,
            session=session,
        )
        refresh_tokens = [
            RefreshTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                created_at=token.created_at,
                version=token.version,
                device_id=token.device_id,
            )
            for token in user.refresh_tokens
        ]
        devices = [token.device_id for token in refresh_tokens]
        return UserFullModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            version=user.version,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
            refresh_tokens=refresh_tokens,
            devices_count=len(devices),
            devices=devices,
        )
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def get_user_by_credendials_from_db(
    user_credentials: UserAuth, session: AsyncSession
) -> UserFromDB:
    """
    Верни пользователя из БД. (вспомогательная функция)

    :param user_credentials: * Pydantic-модель, проверившая корректность введённых
        пользователем данных
    :param session: * объект сессии, для обращения к БД

    :return: * Pydantic-модель пользователя, с имеющимся от БД id

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        user_obj: User = await get_user_by_email(user_credentials.email, session)
        if user_obj is None:
            raise UserNotFoundHTTPException
        user = UserFromDB(
            id=user_obj.id,
            email=user_obj.email,
            hashed_password=user_obj.hashed_password,
            is_active=user_obj.is_active,
            version=user_obj.version,
        )
        if not verify_password(
            user_credentials.password.get_secret_value(),
            user.hashed_password.get_secret_value(),
        ):
            raise UnauthorizedHTTPException
        return user
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def get_user_by_id_from_db(
    user_id: int, session: AsyncSession
) -> UserFromDB | None:
    """
    Верни пользователя из БД по его ID. (вспомогательная функция)

    :param user_id: * идентификатор пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * объект пользователя из БД

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    :raises UserNotFoundHTTPException: * запрашиваемый пользователь не найден,
        выбрось ошибку сервера 404
    """
    try:
        user_obj: User = await get_user_by_id(user_id, session)
        if user_obj is None:
            raise UserNotFoundHTTPException
        user = UserFromDB(
            id=user_obj.id,
            email=user_obj.email,
            hashed_password=user_obj.hashed_password,
            is_active=user_obj.is_active,
            version=user_obj.version,
        )
        return user
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def delete_refresh_token_by_uid_and_devid_from_db(
    user_id: int, device_id: str, session: AsyncSession
) -> None:
    """
    Удали токен пользователя для конкретного устройства. Нестрогое удаление.
        (вспомогательная функция)

    :param user_id: * ID-пользователя в БД
    :param user_version: * версия пользователя (версионирование токенов)
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        return await delete_refresh_token_by_uid_and_devid(
            user_id=user_id, device_id=device_id, session=session
        )
    except RefreshTokenNotFoundError:
        return None
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def change_user_email_from_db(
    email: str, user_id: int, session: AsyncSession
) -> UserFromDB:
    """
    Измени email пользователя. (вспомогательная функция)

    :param email: * новый email (эл. почта, она же аналог username)
    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * pydantic-объект пользователя

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        user: User = await change_user_email(
            email=email, user_id=user_id, session=session
        )
        return UserFromDB(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            version=user.version,
        )
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def change_user_password_from_db(
    password_hash: str, user_id: int, session: AsyncSession
) -> None:
    """
    Измени пароль пользователя. (вспомогательная функция)

    :param password: * новый пароль
    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        user: User = await change_user_password(
            password_hash=password_hash,
            user_id=user_id,
            session=session,
        )
        return UserFromDB(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            version=user.version,
        )
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException


async def soft_delete_user_from_db(user_id: int, session: AsyncSession) -> None:
    """
    Произведи мягкое удаление пользователя
        (изменение полей is_active и deleted_at). (вспомогательная функция)

    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises DBIsNotAvailableHTTPException: * нет соединения с БД,
        выбрось ошибку сервера 500
    """
    try:
        user = await soft_delete_user(
            user_id=user_id,
            session=session,
        )
        return UserFromDB(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            version=user.version,
        )
    except DBIsNotAvailableError:
        raise DBIsNotAvailableHTTPException

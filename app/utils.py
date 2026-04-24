from datetime import datetime, timedelta
from typing import Tuple

import bcrypt
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from fastapi.responses import Response

from app.config import settings
from app.exceptions import InvalidTokenHTTPException, RefreshTokenExpiredHTTPException
from app.models.pydantic import JWTokenModel


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

bcrypt.__about__ = bcrypt
from passlib.context import CryptContext


pwd_context = CryptContext(
    schemes=["argon2"], default="argon2", argon2__default_rounds=20, deprecated="auto"
)


# pem_bytes = ...

# PRIVATE_KEY = serialization.load_pem_private_key(
#     pem_bytes, password=SECRET_KEY, backend=default_backend()
# )
# PUBLIC_KEY = serialization.load_pem_public_key


def get_password_hash(password: str) -> str:
    """
    Верни хеш пароля

    :param password: исходная строка

    :return: хешированный пароль

    :raises: TypeError, ValueError
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Сверь оригинальный пароль с хешем

    :param plain_password: оригинальный пароль
    :param hashed_password: хешированное представление пароля

    :return: True, если пароли совпадают, иначе False

    :raises: TypeError, ValueError
    """
    return pwd_context.verify(plain_password, hashed_password)


def gen_jwt_token_model(data: dict, token_type="access") -> JWTokenModel:
    """
    Сгенерируй и верни JWTokenModel

    :param data: словарь, с некой уже полезной нагрузкой
    :param type: тип токена: access (короткоживущий) или refresh (долгоживущий)
    :return: Pydantic-model, содержащая итоговую закодированную строку JWToken
    """
    if token_type == "access":
        token_expire_minutes = settings.ACCESS_TOKEN_EXPIRES_MINUTES
    else:
        token_expire_minutes = settings.REFRESH_TOKEN_EXPIRES_MINUTES
    copied_data = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=token_expire_minutes)
    version = data.get("version")
    device_id = data.get("device_id")
    copied_data.update(
        {"exp": expire, "type": token_type, "version": version, "device_id": device_id}
    )
    token_hash = jwt.encode(copied_data, SECRET_KEY, algorithm=ALGORITHM)
    return JWTokenModel(
        token_hash=token_hash,
        user_id=data.get("user_id"),
        exp=expire,
        type=token_type,
        version=version,
        device_id=device_id,
    )


def get_pair_of_jwt(data: dict) -> Tuple[JWTokenModel, JWTokenModel]:
    """
    Верни пару токенов

    :param data: словарь с данными

    :return: кортеж из JWToken`ов
    """
    return gen_jwt_token_model(data, "access"), gen_jwt_token_model(data, "refresh")


def _get_payload_from_token(token: str, token_type: str) -> dict:
    """
    Извлеки и верни кортеж, содержащий полезную нагрузку из токена + сам токен
    """
    try:
        payload = jwt.decode(jwt=token, key=SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            raise InvalidTokenHTTPException
        return payload
    except jwt.ExpiredSignatureError:
        raise RefreshTokenExpiredHTTPException
    except jwt.InvalidTokenError:
        raise InvalidTokenHTTPException


def set_token_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    """
    Установи access и refresh токены в cookie пользователю

    :param response: модель ответа пользователю
    :param access_token: короткоживущий jwt-access
    :param refresh_token: долгощивущий jwt-refresh
    """
    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
        domain=settings.SESSION_COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRES_MINUTES * 60,
        domain=settings.SESSION_COOKIE_DOMAIN,
        path="/",
    )
    response.headers.append("WWW-Authenticate", f"Bearer {access_token}")

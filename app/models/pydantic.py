import re
from datetime import datetime
from typing import Annotated, List

from pydantic import (
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    SecretStr,
)


def password_validator(target: str) -> str:
    """
    Проверь пароль на валидность (UPPER_CASE + lower_case + цифра и спец. символ)

    :param target: исходная строка (пароль)
    :return: строка, если прошла проверку
    """
    pattern = re.compile(
        "(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*()_+\-=\[\]{};':\\|,.<>\/?]).+"
    )
    if type(target) != str or re.search(pattern, target) is None:
        raise ValueError(
            "Пароль должен содержать малые и большие буквы, цифру и специальный символ!"
        )
    return target


class UserBase(BaseModel):
    """
    Базовая модель пользователя, содержащая поле Email
        - валидный адрес электронной почты


    :param email: уникальный email пользователя
    """

    email: EmailStr = Field(unique=True)

class PasswordModel(BaseModel):
    """
    Модель, проверяющее поле с паролем (для подтверждения действий в эндпоинте)

    :param password: 8-30символов UPPER_CASE + lower_case + цифра и спец. символ
    """

    password: Annotated[
        SecretStr,
        Field(..., min_length=8, max_length=30, exclude=True),
        BeforeValidator(password_validator),
    ]

class UserAuth(UserBase, PasswordModel):
    """
    Модель пользователя для проверки на соответствие входных данных.
    :param email: уникальный электронный адрес
    :param password: 8-30символов UPPER_CASE + lower_case + цифра и спец. символ
    """


class PasswordsModel(PasswordModel):
    """
    Модель, с полем для нового пароля и паролем, подтверждающим действия
        пользователя

    :param new_password: 8-30символов UPPER_CASE + lower_case + цифра и спец. символ
    """

    new_password: Annotated[
        SecretStr,
        Field(..., min_length=8, max_length=30, exclude=True),
        BeforeValidator(password_validator),
    ]


class UserToDB(UserBase):
    """
    Модель, для отправки в БД

    :param hashed_password: поле для хеша пароля, скрытого от глаз пользователя
        (для вывода хеша пароля, требуется обратиться к полю через спец. метод)
    """

    hashed_password: SecretStr = Field(exclude=True, repr=False)


class UserFromDB(UserToDB):
    """
    Модель пользователя из БД, имеющая дополнительные поля

    :param id: Идентификационный номер пользователя в БД
    :param is_active: поле, позволяющее определить активный пользователь
        (разрешено использование) или же нет (запрещено/заблокирован/удалён)
    :param version: поле, определяющее версию клиента (изменяется при каждом
        изменении учётных данных, инвалидирующее выданные токены)
    """

    id: int
    is_active: bool
    version: int


class UserFullModel(UserFromDB):
    """
    Полная модель пользователя из БД

    :param created_at: дата создания/регистрации аккаунта
    :param updated_at: дата последнего обновления учётных данных
    :param deleted_at: дата удаления аккаунта (если было удаление)
    :param refresh_tokens: список рефреш-токенов (Pydantic-модель)
    :devices_count: количество активных устройств
    :devices: список идентификаторов устройств
    """

    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    refresh_tokens: List["RefreshTokenModel"]
    devices_count: int
    devices: List[str]


class ErrorResponseModel(BaseModel):
    """
    Модель, для передачи экземпляра ошибки в последющую обработку

    :param status_code: HTTP-код ответа
    :param detail: краткая информация, пересылаемая пользователю
    :param message: краткая информация, предназаченная для логгирования
    """

    status_code: int
    detail: str
    message: str


class JWTokenModel(BaseModel):
    """
    :param token_hash: итоговый хэш jwt
    :param user_id: id-пользователя в БД (аналог sub)
    :param exp: дата истечения токена
    :param version: номер версии. для сравнения с версией пользователя
        (дополнительный механизм проверки)
    :param device_id: ID-устройства, на которое выдан токен
    :param type: тип токена: access или refresh
    """

    token_hash: str
    user_id: int
    exp: datetime
    version: int
    device_id: str
    type: str  # access or refresh


class RefreshTokenModel(BaseModel):
    """
    :param id: ID-токена в БД
    :param user_id: ID-пользователя в БД (владелец)
    :param token_hash: хеш токена (кодированная строка)
    :param expires_at: дата истечения токена
    :param created_at: дата создания токена
    :param version: номер версии. для сравнения с версией пользователя
        (дополнительный механизм проверки)
    :param device_id: ID-устройства, на которое выдан токен
    """

    id: int
    user_id: int
    token_hash: str
    expires_at: datetime
    created_at: datetime
    version: int
    device_id: str

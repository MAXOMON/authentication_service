from sqlalchemy import delete, exc, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import DBIsNotAvailableError, RefreshTokenNotFoundError
from app.models.db_tables import RefreshToken, User
from app.models.pydantic import JWTokenModel, UserToDB


async def add_or_update_refresh_token(
    refresh_token: JWTokenModel, session: AsyncSession
) -> None:
    """
    Добавь или обнови уже существущий рефреш-токен пользователя, выданный
        на конкретное устройство.

    :param refresh_token: * pydantic-модель с данными рефреш-токена
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        # удали истёкшие токены
        await session.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == refresh_token.user_id,
                RefreshToken.expires_at < func.timezone("UTC", func.now()),
            )
        )
        # найди существующий токен
        existing_token = await session.scalar(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == refresh_token.user_id,
                RefreshToken.device_id == refresh_token.device_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        if existing_token:
            # вставка с обновлением
            statement = (
                insert(RefreshToken)
                .values(
                    user_id=refresh_token.user_id,
                    token_hash=refresh_token.token_hash,
                    expires_at=refresh_token.exp,
                    version=refresh_token.version,
                    device_id=refresh_token.device_id,
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "device_id"],
                    set_=dict(
                        token_hash=refresh_token.token_hash,
                        expires_at=refresh_token.exp,
                        version=refresh_token.version,
                    ),
                )
            )
            await session.execute(statement)
        else:
            # вставка нового, с очисткой старого, при превышении лимита
            result = await session.execute(
                select(RefreshToken)
                .where(RefreshToken.user_id == refresh_token.user_id)
                .order_by(RefreshToken.created_at.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            active_tokens = result.scalars().all()

            if len(active_tokens) >= settings.MAX_SESSIONS:
                await session.delete(active_tokens[0])  # самый старый токен

            session.add(
                RefreshToken(
                    user_id=refresh_token.user_id,
                    token_hash=refresh_token.token_hash,
                    expires_at=refresh_token.exp,
                    version=refresh_token.version,
                    device_id=refresh_token.device_id,
                )
            )

        await session.commit()
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def get_full_user_information(user_id: int, session: AsyncSession) -> User:
    """
    Верни полную информацию о пользователе из БД.

    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * объект пользователя из БД, со связанными данными

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        """
        SELECT
            u.id,
            u.email,
            u.hashed_password,
            u.is_active,
            u.created_at,
            u.updated_at,
            u.deleted_at,
            u.version,
            COALESCE(
                json_agg(
                    json_build_object(
                        'id', rt.id,
                        'token_hash', rt.token_hash,
                        'expires_at', rt.expires_at,
                        'created_at', rt.created_at,
                        'device_id', rt.device_id,
                        'version', rt.version
                    ) ORDER BY rt.created_at
                ) FILTER (WHERE rt.id IS NOT NULL),
                '[]'
            ) AS refresh_tokens,
            COALESCE(
                array_agg(DISTINCT rt.device_id) FILTER (WHERE rt.device_id IS NOT NULL),
                '{}'
            ) AS devices,
            COUNT(DISTINCT rt.device_id) AS devices_count
        FROM users u
        LEFT JOIN refreshtokens rt ON u.id = rt.user_id
        WHERE u.id = :user_id
        GROUP BY u.id
        """
        # result = await session.execute(query, {"user_id": user_id})
        # row = result.one()

        # # row.refresh_tokens — это уже список словарей (JSON)
        # # Преобразуем его в список Pydantic-моделей
        # refresh_tokens_models = [
        #   RefreshTokenModel(**token) for token in row.refresh_tokens]
        result = await session.execute(
            select(User)
            .options(selectinload(User.refresh_tokens))
            .where(User.id == user_id)
        )
        return result.scalar()
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def get_user_by_id(user_id: int, session: AsyncSession) -> User | None:
    """
    Получи пользователя из БД

    :param user_id: * число, уникальный id пользователя
    :param session: * объект сессии, для обращения к БД

    :return: * модель из БД (необходимо преобразовать)

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        user = await session.get(User, user_id)
        return user
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def get_user_by_email(email: str, session: AsyncSession) -> User | None:
    """
    Получи пользователя из БД

    :param email: * строка, уникальный email пользователя
    :param session: * объект сессии, для обращения к БД

    :return: * модель из БД (необходимо преобразовать)

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        user = await session.scalar(select(User).filter(User.email == email))
        return user
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def add_user(user: UserToDB, session: AsyncSession) -> UserToDB:
    """
    Добавь модель пользователя в БД

    :param user: * pydantic-модель пользователя
    :param session: * объект сессии, для обращения к БД

    :return: * pydantic-модель пользователя

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        session.add(
            User(
                email=user.email,
                hashed_password=user.hashed_password.get_secret_value(),
            )
        )
        await session.commit()
        return user
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def get_refresh_token(token_hash: str, session: AsyncSession) -> RefreshToken:
    """
    Верни конкретный рефреш-токен пользователя из БД

    :param token_hash: * кодированная строка токена
    :param session: * объект сессии, для обращения к БД

    :return: * объект токена в БД

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        return await session.scalar(
            select(RefreshToken).filter(RefreshToken.token_hash == token_hash)
        )
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def get_refresh_token_by_uid_and_devid(
    user_id: int, device_id: str, session: AsyncSession
) -> RefreshToken | None:
    """
    Верни рефреш-токен пользователя конкретного устройства из БД

    :param user_id: * ID-пользователя в БД
    :param device_id: * идентификатор устройства
    :param session: * объект сессии, для обращения к БД

    :return: * объект токена в БД

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        return await session.scalar(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.device_id == device_id
            )
        )
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


# async def delete_refresh_token(
#     refresh_token: RefreshToken, session: AsyncSession
# ) -> None:
#     """
#     Удали переданный рефреш-токен из БД

#     :param refresh_token: * объект рефреш-токена из БД
#     :param session: * объект сессии, для обращения к БД

#     :return: ``None``

#     :raises RefreshTokenNotFoundError: * рефреш-токен не был найден в БД
#     :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
#     """
#     try:
#         await session.delete(refresh_token)
#         await session.commit()
#     except exc.NoResultFound:
#         raise RefreshTokenNotFoundError
#     except (exc.OperationalError, ConnectionRefusedError):
#         raise DBIsNotAvailableError


async def delete_refresh_token_by_uid_and_devid(
    user_id: int, device_id: str, session: AsyncSession
) -> None:
    """
    Удали токены пользователя для конкретного устройства

    :param user_id: * ID-пользователя в БД
    :param user_version: * версия пользователя (версионирование токенов)
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises RefreshTokenNotFoundError: * рефреш-токен не был найден в БД
    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        await session.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.device_id == device_id
            )
        )
        await session.commit()
    except exc.NoResultFound:
        raise RefreshTokenNotFoundError
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def delete_all_user_refresh_tokens(user_id: int, session: AsyncSession) -> None:
    """
    Удали все токены пользователя и инкрементируй версию пользователя, чтобы
        и access-токены инвалидировались

    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: ``None``

    :raises RefreshTokenNotFoundError: * рефреш-токен не был найден в БД
    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        now = func.timezone("UTC", func.now())
        await session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                version=User.version + 1,
                updated_at=now
            )
        )
        await session.commit()
    except exc.NoResultFound:
        raise RefreshTokenNotFoundError
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def change_user_email(email: str, user_id: int, session: AsyncSession) -> User:
    """
    Измени email пользователя

    :param email: * новый email (эл. почта, она же аналог username)
    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * объект пользователя из БД

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """

    try:
        user = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                email=email,
                version=User.version + 1,
                updated_at=func.timezone("UTC", func.now()),
            )
            .returning(User)
        )
        await session.commit()
        return user.scalar()
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def change_user_password(
    password_hash: str, user_id: int, session: AsyncSession
) -> None:
    """
    Измени пароль пользователя

    :param password_hash: * новый хэш пароля
    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * объект пользователя из БД

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """

    try:
        user = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                hashed_password=password_hash,
                version=User.version + 1,
                updated_at=func.timezone("UTC", func.now()),
            )
            .returning(User)
        )
        await session.commit()
        return user.scalar()
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError


async def soft_delete_user(user_id: int, session: AsyncSession) -> None:
    """
    Произведи мягкое удаление пользователя
        (изменение полей is_active и version)

    :param user_id: * ID-пользователя в БД
    :param session: * объект сессии, для обращения к БД

    :return: * объект пользователя из БД

    :raises DBIsNotAvailableError: * нет соединения с БД (БД недоступна)
    """
    try:
        now = func.timezone("UTC", func.now())
        user = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                is_active=False,
                version=User.version + 1,
                updated_at=now,
                deleted_at=now,
            )
            .returning(User)
        )
        await session.commit()
        return user.scalar()
    except (exc.OperationalError, ConnectionRefusedError):
        raise DBIsNotAvailableError

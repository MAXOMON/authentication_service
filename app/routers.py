from typing import Tuple

from fastapi import APIRouter, Body, Depends, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response
from fastapi_device_id import compare_device_ids, get_device_id
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.config import settings
from app.database import get_session
from app.depends import (add_or_update_refresh_token_to_db, add_user_to_db, change_user_email_from_db,
                         change_user_password_from_db, delete_all_user_refresh_tokens_from_db,
                         delete_refresh_token_by_uid_and_devid_from_db, get_and_check_credentials,
                         get_full_user_information_from_db, get_payload_from_access_token,
                         get_payload_from_refresh_token, get_refresh_token_from_db, get_user_by_credendials_from_db,
                         get_user_by_email_from_db, get_user_by_id_from_db, soft_delete_user_from_db,)
from app.exceptions import (EmailDoesntMatchHTTPException, InvalidTokenHTTPException, PasswordMatchHTTPException,
                            UnauthorizedHTTPException, UserAlreadyExistsHTTPException,)
from app.models.db_tables import RefreshToken
from app.models.pydantic import PasswordModel, PasswordsModel, UserAuth, UserFromDB, UserToDB
from app.utils import get_pair_of_jwt, get_password_hash, set_token_cookies, verify_password


router = APIRouter(prefix="/auth")


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_REGISTER, hours=1))],
)
async def post_register(
    user: UserAuth = Depends(get_and_check_credentials),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if await get_user_by_email_from_db(user.email, session) is not None:
        raise UserAlreadyExistsHTTPException
    await add_user_to_db(
        UserToDB(
            email=user.email,
            hashed_password=get_password_hash(user.password.get_secret_value()),
        ),
        session,
    )
    return {"message": "Register successful"}


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_LOGIN_OR_REFRESH, hours=1)),
    ],
)
async def post_login(
    request: Request,
    response: Response,
    user_credentials: UserAuth = Depends(get_and_check_credentials),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:

    user: UserFromDB = await get_user_by_credendials_from_db(user_credentials, session)
    if not user.is_active:
        raise UnauthorizedHTTPException
    device_id = get_device_id(request)
    data = {"user_id": user.id, "version": user.version, "device_id": device_id}

    access_token, refresh_token = get_pair_of_jwt(data)
    await add_or_update_refresh_token_to_db(refresh_token, session)
    set_token_cookies(response, access_token.token_hash, refresh_token.token_hash)
    return {"message": "Login successful"}


@router.post(
    "/refresh",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_LOGIN_OR_REFRESH, hours=1)),
    ],
)
async def post_refresh(
    request: Request,
    response: Response,
    data: Tuple[dict, str] = Depends(get_payload_from_refresh_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload, token = data
    device_id = get_device_id(request)

    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not user.is_active:
        raise UnauthorizedHTTPException

    refresh_token_from_db: RefreshToken = await get_refresh_token_from_db(
        token_hash=token, session=session
    )
    if not (
        (refresh_token_from_db is not None)
        and (compare_device_ids(refresh_token_from_db.device_id, device_id))
        and (refresh_token_from_db.version == user.version)
    ):
        raise InvalidTokenHTTPException

    data = {"user_id": user.id, "version": user.version, "device_id": device_id}

    access_token, refresh_token = get_pair_of_jwt(data)
    await add_or_update_refresh_token_to_db(refresh_token, session)
    set_token_cookies(response, access_token.token_hash, refresh_token.token_hash)
    return {"message": "Refreshing successful!"}


@router.post(
    "/user/logout",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_USER_CHANGES, minutes=15)),
    ],
)
async def post_logout(
    request: Request,
    response: Response,
    data: Tuple[dict, str] = Depends(get_payload_from_access_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload, _ = data
    device_id = get_device_id(request)
    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not user.is_active:
        raise UnauthorizedHTTPException

    if not (
        compare_device_ids(payload.get("device_id"), device_id)
        and (payload.get("version") == user.version)
    ):
        raise InvalidTokenHTTPException

    await delete_refresh_token_by_uid_and_devid_from_db(
        user_id=user.id,
        device_id=device_id,
        session=session,
    )
    response.delete_cookie("access_token")
    return {"message": "Logout successful!"}


@router.post(
    "/user/close_all_sessions",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_USER_CHANGES, minutes=30)),
    ],
)
async def post_close_all_sessions(
    request: Request,
    response: Response,
    data: Tuple[dict, str] = Depends(get_payload_from_access_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload, _ = data
    device_id = get_device_id(request)

    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not user.is_active:
        raise UnauthorizedHTTPException

    if not (
        compare_device_ids(payload.get("device_id"), device_id)
        and (payload.get("version") == user.version)
    ):
        raise InvalidTokenHTTPException

    await delete_all_user_refresh_tokens_from_db(user.id, session)
    response.delete_cookie("access_token")
    return {"message": "Closing the all sessions successful!"}


@router.post(
    "/user/change_email",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_USER_CHANGES, hours=24))
    ],
)
async def post_change_user_email(
    request: Request,
    new_user_data: UserAuth = Body(...),
    data: Tuple[dict, str] = Depends(get_payload_from_access_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload, _ = data
    device_id = get_device_id(request)
    new_email, password = new_user_data.email, new_user_data.password

    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not (
        user.is_active
        and verify_password(
            password.get_secret_value(), user.hashed_password.get_secret_value()
        )
    ):
        raise UnauthorizedHTTPException

    if not (
        compare_device_ids(payload.get("device_id"), device_id)
        and (payload.get("version") == user.version)
    ):
        raise InvalidTokenHTTPException

    if await get_user_by_email_from_db(new_email, session) is not None:
        raise UserAlreadyExistsHTTPException

    await change_user_email_from_db(email=new_email, user_id=user.id, session=session)
    return {"message": "Email changed successful"}


@router.post(
    "/user/change_password",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_USER_CHANGES, hours=24))
    ],
)
async def post_change_user_password(
    request: Request,
    new_user_data: PasswordsModel = Body(...),
    data: Tuple[dict, str] = Depends(get_payload_from_access_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload, _ = data
    device_id = get_device_id(request)

    new_password, password = new_user_data.new_password, new_user_data.password
    if new_password.get_secret_value() == password.get_secret_value():
        raise PasswordMatchHTTPException

    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not (
        user.is_active
        and verify_password(
            password.get_secret_value(), user.hashed_password.get_secret_value()
        )
    ):
        raise UnauthorizedHTTPException

    if not (
        compare_device_ids(payload.get("device_id"), device_id)
        and (payload.get("version") == user.version)
    ):
        raise InvalidTokenHTTPException

    await change_user_password_from_db(
        password_hash=get_password_hash(new_password.get_secret_value()),
        user_id=user.id,
        session=session,
    )
    return {"message": "Password changed successful"}


@router.delete(
    "/user/profile",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_USER_CHANGES, hours=24))
    ],
)
async def delete_profile(
    request: Request,
    new_user_data: UserAuth = Body(...),
    data: Tuple[dict, str] = Depends(get_payload_from_access_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload, _ = data
    device_id = get_device_id(request)
    email_for_deletion, password = new_user_data.email, new_user_data.password

    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not (
        user.is_active
        and verify_password(
            password.get_secret_value(), user.hashed_password.get_secret_value()
        )
    ):
        raise UnauthorizedHTTPException

    if not (
        compare_device_ids(payload.get("device_id"), device_id)
        and (payload.get("version") == user.version)
    ):
        raise InvalidTokenHTTPException

    if email_for_deletion != user.email:
        raise EmailDoesntMatchHTTPException

    await soft_delete_user_from_db(
        user_id=user.id,
        session=session,
    )
    return {"message": "Soft-deleting successful"}


@router.get(
    "/user/profile",
    dependencies=[
        Depends(RateLimiter(times=settings.RATE_LIMIT_GET_USER_INFO, hours=1))
    ],
)
async def get_profile(
    request: Request,
    password_model: PasswordModel = Body(...),
    data: Tuple[dict, str] = Depends(get_payload_from_access_token),
    session: AsyncSession = Depends(get_session),
):
    payload, _ = data
    device_id = get_device_id(request)

    user: UserFromDB = await get_user_by_id_from_db(payload.get("user_id"), session)
    if not (
        user.is_active
        and verify_password(
            password_model.password.get_secret_value(),
            user.hashed_password.get_secret_value(),
        )
    ):
        raise UnauthorizedHTTPException

    if not (
        compare_device_ids(payload.get("device_id"), device_id)
        and (payload.get("version") == user.version)
    ):
        raise InvalidTokenHTTPException

    return await get_full_user_information_from_db(
        user_id=payload.get("user_id"), session=session
    )

from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.exceptions import ConnectionError
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi_device_id import DeviceMiddleware
from fastapi_limiter import FastAPILimiter

from app.config import settings
from app.exceptions import (DBIsNotAvailableHTTPException, EmailDoesntMatchHTTPException,
                            InvalidCredentialsHTTPException, InvalidTokenHTTPException, PasswordMatchHTTPException,
                            RefreshTokenExpiredHTTPException, UnauthorizedHTTPException, UserAlreadyExistsHTTPException,
                            UserNotFoundHTTPException, db_is_not_available_exception_handler,
                            email_doesnt_match_exception_handler, invalid_credentials_exception_handler,
                            invalid_token_exception_handler, password_match_exception_handler,
                            refresh_token_expired_exception_handler, request_validation_exception_handler,
                            standart_http_exception_handler, unauthorized_user_exception_handler,
                            user_already_exists_exception_handler, user_not_found_exception_handler,)
from app.routers import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    redis_connection = redis.from_url(settings.REDIS_URL, encoding="utf-8")
    await FastAPILimiter.init(redis_connection)
    yield
    await FastAPILimiter.close()



app = FastAPI(docs_url=None, openapi_url=None, redoc_url=None, lifespan=lifespan)

app.debug = settings.DEBUG

origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(
    DeviceMiddleware,
    cookie_name="device_id",
    cookie_max_age=365 * 24 * 60 * 60,
    cookie_secure=settings.SESSION_COOKIE_SECURE,
    cookie_samesite=settings.SAMESITE,
)


app.include_router(router)

# app.add_exception_handler(класс_исключения, функция_обработчик_исключения)
app.add_exception_handler(
    DBIsNotAvailableHTTPException, db_is_not_available_exception_handler
)
app.add_exception_handler(
    EmailDoesntMatchHTTPException, email_doesnt_match_exception_handler
)
app.add_exception_handler(
    InvalidCredentialsHTTPException, invalid_credentials_exception_handler
)
app.add_exception_handler(InvalidTokenHTTPException, invalid_token_exception_handler)
app.add_exception_handler(PasswordMatchHTTPException, password_match_exception_handler)
app.add_exception_handler(
    RefreshTokenExpiredHTTPException, refresh_token_expired_exception_handler
)
app.add_exception_handler(
    UnauthorizedHTTPException, unauthorized_user_exception_handler
)
app.add_exception_handler(
    UserAlreadyExistsHTTPException, user_already_exists_exception_handler
)
app.add_exception_handler(UserNotFoundHTTPException, user_not_found_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

app.add_exception_handler(HTTPException, standart_http_exception_handler)
app.add_exception_handler(Exception, standart_http_exception_handler)

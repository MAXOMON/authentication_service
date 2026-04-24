import logging

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

import app.logging_config
from app.models.pydantic import ErrorResponseModel


logger = logging.getLogger(__name__)

# кастомные классы исключений


class AppError(Exception):
    """Базовая ошибка приложения"""


class DBIsNotAvailableError(AppError):
    """БД недоступна"""


class RefreshTokenNotFoundError(AppError):
    """Рефреш-токен не найден или отозван"""


# HTTPExceptions


class DBIsNotAvailableHTTPException(HTTPException):
    """База данных недоступна 500"""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "Internal Server Error",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "DATABASE IS NOT AVAILABLE"


class EmailDoesntMatchHTTPException(HTTPException):
    """Email`ы не совпадают 409"""

    def __init__(
        self,
        status_code: int = status.HTTP_409_CONFLICT,
        detail: str = "Email doesn`t match!",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "Deleting user-account failed"


class InvalidCredentialsHTTPException(HTTPException):
    """Имя пользователя и пароль не прошли проверку 401"""

    def __init__(
        self,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        detail: str = "Invalid Credentials",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "401 INVALID CREDENTIALS"


class InvalidTokenHTTPException(HTTPException):
    """Использование невалидного JWT 401"""

    def __init__(
        self,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        detail: str = "Invalid Token",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "Invalid Token Using"


class PasswordMatchHTTPException(HTTPException):
    """Совпадение паролей 409"""

    def __init__(
        self,
        status_code: int = status.HTTP_409_CONFLICT,
        detail: str = "Passwords must be different!",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "Matching passwords"


class RefreshTokenExpiredHTTPException(HTTPException):
    """Рефреш-токен истек 401"""

    def __init__(
        self,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        detail: str = "Expired signature",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "Expired Token Using"


class UnauthorizedHTTPException(HTTPException):
    """Ошибка авторизации пользователя 401"""

    def __init__(
        self,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        detail: str = "Authorization error",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "401 UNAUTHORIZED"


class UserAlreadyExistsHTTPException(HTTPException):
    """Пользователь уже существует 409"""

    def __init__(
        self,
        status_code: int = status.HTTP_409_CONFLICT,
        detail: str = "User already exists",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "409 User already exists"


class UserNotFoundHTTPException(HTTPException):
    """Запрашиваемый пользователь не найден 404"""

    def __init__(
        self,
        status_code: int = status.HTTP_404_NOT_FOUND,
        detail: str = "User not found",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = "User not found"


# обработчики исключений, с логгированием


async def db_is_not_available_exception_handler(
    request: Request, exc: DBIsNotAvailableHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.critical(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def email_doesnt_match_exception_handler(
    request: Request,
    exc: EmailDoesntMatchHTTPException,
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.info(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def invalid_credentials_exception_handler(
    request: Request, exc: InvalidCredentialsHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.info(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
        headers={"WWW-Authenticate": "Basic"},
    )


async def invalid_token_exception_handler(
    request: Request, exc: InvalidTokenHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def password_match_exception_handler(
    request: Request,
    exc: PasswordMatchHTTPException,
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.debug(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def refresh_token_expired_exception_handler(
    request: Request, exc: RefreshTokenExpiredHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def user_not_found_exception_handler(
    request: Request, exc: UserNotFoundHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.info(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=404,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def unauthorized_user_exception_handler(
    request: Request, exc: UnauthorizedHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
        headers={"WWW-Authenticate": "Basic"},
    )


async def user_already_exists_exception_handler(
    request: Request, exc: UserAlreadyExistsHTTPException
) -> JSONResponse:
    error: dict = jsonable_encoder(
        ErrorResponseModel(
            status_code=exc.status_code, detail=exc.detail, message=exc.message
        )
    )
    logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "detail": exc.detail},
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "status_code": 422,
            "message": "Validation error",
            "detail": [
                {"field": err["loc"][-1], "message": err["msg"]} for err in exc.errors()
            ],
        },
    )


async def standart_http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    if isinstance(exc, HTTPException):
        if exc.status_code == 429:
            error: dict = jsonable_encoder(
                ErrorResponseModel(
                    status_code=exc.status_code,
                    detail=exc.detail,
                    message="Request limit exceeded",
                )
            )
            logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
            return JSONResponse(
                status_code=exc.status_code,
                content={"status_code": exc.status_code, "detail": exc.detail},
                headers=exc.headers,
            )
        else:
            error: dict = jsonable_encoder(
                ErrorResponseModel(
                    status_code=exc.status_code,
                    detail=exc.detail,
                    message="Internal server error",
                )
            )
            logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
            return JSONResponse(
                status_code=exc.status_code,
                content={"status_code": exc.status_code, "detail": "Internal server error"},
                headers=exc.headers,
            )
    else:
        error: dict = jsonable_encoder(
            ErrorResponseModel(
                status_code=500,
                detail=str(exc),
                message="Internal server error"
            )
        )
        logger.warning(error | dict(ip=request.client.host + f":{request.client.port}"))
        return JSONResponse(
            status_code=500,
            content={"status_code": 500, "detail": "Internal server error"}
        )

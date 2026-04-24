import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    _secret_key: str | None = None

    # MAIN
    DEBUG: bool

    # SECURITY
    ALGORITHM: str
    SECRET_KEY: str = ""

    # DATABASE

    DB_DRIVER_NAME: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_IP_ADDRESS: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    DATABASE_URL: str

    # REDIS
    REDIS_PASSWORD: str
    REDIS_PORT: int
    REDIS_URL: str

    # JWT
    ACCESS_COOKIE_NAME: str
    ACCESS_TOKEN_EXPIRES_MINUTES: int
    REFRESH_COOKIE_NAME: str
    REFRESH_TOKEN_EXPIRES_MINUTES: int
    SESSION_COOKIE_SECURE: bool
    SAMESITE: str
    SESSION_COOKIE_DOMAIN: str
    MAX_SESSIONS: int

    # RATE_LIMITER
    RATE_LIMIT_REGISTER: int
    RATE_LIMIT_LOGIN_OR_REFRESH: int
    RATE_LIMIT_USER_CHANGES: int
    RATE_LIMIT_GET_USER_INFO: int

    @property
    def SECRET_KEY(self) -> str:
        if self._secret_key is None:
            self._secret_key = secrets.token_hex(32)
        return self._secret_key

    @SECRET_KEY.setter
    def SECRET_KEY(self, value: str) -> None:
        if type(value) != str:
            raise ValueError("Значение для SECRET_KEY должно быть строкой!")
        self._secret_key = value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

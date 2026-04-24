from datetime import datetime, timedelta

import jwt
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.depends import add_or_update_refresh_token_to_db
from app.models.db_tables import User
from app.models.pydantic import JWTokenModel
from app.utils import get_password_hash
from tests.fixtures.constants import DEVICE_ID, USER_EMAIL, USER_PASSWORD


TOKEN_ERROR_CASES = [
    {
        "id": "wrong_signature",
        "token_params": {"secret_key": "WrongSecret"},
        "expected_detail": "Invalid Token",
    },
    {
        "id": "expired",
        "token_params": {"expiration_minutes": -1},
        "expected_detail": "Expired signature",
    },
    {
        "id": "wrong_type",
        "token_params": {"token_type": "refresh"},
        "expected_detail": "Invalid Token",
    },
    {
        "id": "wrong_version",
        "token_params": {"version": 99},
        "expected_detail": "Invalid Token",
    },
    {"id": "another_device", "token_params": {}, "expected_detail": "Invalid Token"},
]


def create_token_model(
    user_id: int,
    token_type: str = "access",
    expiration_minutes: int = 1,
    device_id: str = DEVICE_ID,
    version: int = 0,
    algorithm: str = "HS256",
    secret_key: str = None,
) -> JWTokenModel:
    if secret_key is None:
        secret_key = settings.SECRET_KEY
    expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
    data = {
        "user_id": user_id,
        "exp": expiration_time,
        "type": token_type,
        "version": version,
        "device_id": device_id,
    }
    token_hash = jwt.encode(data, key=secret_key, algorithm=algorithm)
    return JWTokenModel(
        token_hash=token_hash,
        user_id=user_id,
        exp=expiration_time,
        type=token_type,
        version=version,
        device_id=device_id,
    )


async def add_refresh_token_to_db(refresh_token: JWTokenModel, session: AsyncSession):
    if refresh_token.type != "refresh":
        raise ValueError("Токен должен быть refresh")
    await add_or_update_refresh_token_to_db(refresh_token, session)


@pytest_asyncio.fixture
async def correct_access_token(session: AsyncSession):
    user = User(
        email=USER_EMAIL,
        hashed_password=get_password_hash(USER_PASSWORD),
    )
    session.add(user)
    await session.flush()
    access_token: JWTokenModel = create_token_model(user.id)
    await session.commit()
    yield access_token

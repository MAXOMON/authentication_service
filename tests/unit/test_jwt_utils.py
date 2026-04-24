from datetime import datetime, timedelta
from typing import Tuple
import jwt
import pytest
from freezegun import freeze_time


from app.exceptions import InvalidTokenHTTPException, RefreshTokenExpiredHTTPException
from app.models.pydantic import JWTokenModel
from app.utils import _get_payload_from_token, get_pair_of_jwt

from tests.fixtures.tokens import create_token_model



@freeze_time("2026-01-01 12:00:00")
def test_get_payload_from_token_success():
    SECRET_KEY = "any_secret_key"
    ALGORITHM = "HS256"
    # предварительные данные токена
    token_expire_minutes = 15
    user_id = 1
    version = 0
    token_type = "access"
    device_id = "fake_id"
    exp = datetime.utcnow() + timedelta(minutes=token_expire_minutes)

    data: dict = {
        "user_id": user_id,
        "version": version,
        "device_id": device_id,
        "type": token_type,
        "exp": exp
    }
    # генерация токена
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    # проверка валидности
    payload = jwt.decode(jwt=token, key=SECRET_KEY, algorithms=[ALGORITHM])
    # проверки содержимого токена
    assert payload.get("user_id") == user_id
    assert payload.get("version") == version
    assert payload.get("device_id") == device_id
    assert payload.get("type") == token_type
    # проверка времени истечения, без его превышения
    assert payload.get("exp") == exp.timestamp()

def test_get_payload_from_token_wrong_type():
    refresh_token = create_token_model(
        user_id=1,
        token_type="refresh",
        expiration_minutes=1
    )
    with pytest.raises(InvalidTokenHTTPException) as exc:
        _get_payload_from_token(refresh_token.token_hash, "access")
    assert exc.value.status_code == 401

def test_get_payload_from_corrupted_token():
    corrupted_token = create_token_model(1, secret_key="WrongSecretKey")
    with pytest.raises(InvalidTokenHTTPException) as exc:
        _get_payload_from_token(corrupted_token.token_hash, "access")
    assert exc.value.status_code == 401

def test_get_payload_from_expired_token():
    expired_token = create_token_model(user_id=1, expiration_minutes=-1)
    with pytest.raises(RefreshTokenExpiredHTTPException) as exc:
        _get_payload_from_token(expired_token.token_hash, "access")
    assert exc.value.detail == "Expired signature"

def test_get_pair_of_jwt_success():
    data = {
        "user_id": 1,
        "version": 0,
        "device_id": "fake_id",
    }
    pair_of_jwt: Tuple[JWTokenModel, JWTokenModel] = get_pair_of_jwt(data)
    assert isinstance(pair_of_jwt, Tuple)
    access_token, refresh_token = pair_of_jwt
    assert isinstance(access_token, JWTokenModel)
    access_payload = _get_payload_from_token(access_token.token_hash, "access")
    refresh_payload = _get_payload_from_token(refresh_token.token_hash, "refresh")
    assert access_payload.get("exp") != refresh_payload.get("ext")





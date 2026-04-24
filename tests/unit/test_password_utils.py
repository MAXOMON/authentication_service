import pytest
from app.models.pydantic import password_validator, PasswordModel
from app.utils import get_password_hash, verify_password


def test_password_validation_success():
    password = password_validator("Secure123!")  # пароль удовлетворяет условиям
    assert isinstance(password, str)

def test_password_validation_failed():
    passwords = [
        "",
        "lowercasepassword",
        "UPPERCASEPASSWORD",
        "12312412412412414",
        "@_+$@+$@_%+_+@_@%+_",
        "INCORRECTPASSWORD123!"
    ]
    for password in passwords:
        with pytest.raises(ValueError) as exc:
            password_validator(password)
        assert exc.value.args[0] == "Пароль должен содержать малые и большие буквы, цифру и специальный символ!"

def test_password_validation_with_wrong_type():
    with pytest.raises(ValueError) as exc:
        password_validator(1)
    assert exc.value.args[0] == "Пароль должен содержать малые и большие буквы, цифру и специальный символ!"

def test_convert_password_to_password_model_success():
    passwords = [
        "CorrectPassword1!",
        "cOr rect pass word321+-",
        "AWEsome555+55=610"
    ]
    for password in passwords:
        pwd_model = PasswordModel(password=password_validator(password))
        assert pwd_model.password.get_secret_value() == password

def test_convert_password_to_password_model_failed():
    passwords = [
        "",
        "shorter",
        "llllllllooooooooonnnnnnnnngggggggggeeeeeeeeeeerrrrrrrrrrrrrPWD123454321!@#$%",
        "lowercasepassword",
        "UPPERCASEPASSWORD",
        "12312412412412414",
        "@_+$@+$@_%+_+@_@%+_",
        "INCORRECTPASSWORD123!"
    ]
    for password in passwords:
        with pytest.raises((ValueError, TypeError)) as exc:
            PasswordModel(password=password_validator(password))
        assert exc.errisinstance(ValueError) or exc.errisinstance(TypeError)

def test_get_password_hash_success():
    password = PasswordModel(password=password_validator("Secure123!")).password.get_secret_value()
    password_hash = get_password_hash(password)
    assert password != password_hash
    assert type(password) == str and type(password_hash) == str
    second_password_hash = get_password_hash(password)
    assert password_hash != second_password_hash

def test_get_password_hash_failed_with_wrong_type():
    passwords = [
        1,
        int,
        {"black": "white"},
        TypeError,
    ]
    for password in passwords:
        with pytest.raises((ValueError, TypeError)) as exc:
            password_hash = get_password_hash(password)
        assert exc.errisinstance(ValueError) or exc.errisinstance(TypeError)

def test_verify_password_success():
    password = "Secure123!"
    password_hash = get_password_hash(password)
    assert verify_password(password, password_hash)

def test_verify_password_failed():
    password = "Secure123!"
    password_hash = get_password_hash(password)
    another_password = "pASSword890+"
    assert not verify_password(another_password, password_hash)

def test_verify_password_failed_with_wrong_type():
    original_password = "Secure123!"
    passwords = [
        1,
        int,
        {"black": "white"},
        TypeError,
    ]
    for password in passwords:
        with pytest.raises((ValueError, TypeError)) as exc:
            verify_password(original_password, password)
        assert exc.errisinstance(ValueError) or exc.errisinstance(TypeError)

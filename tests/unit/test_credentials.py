import pytest
from pydantic import BaseModel

from app.depends import get_and_check_credentials
from app.exceptions import InvalidCredentialsHTTPException
from app.models.pydantic import UserAuth

from tests.fixtures.constants import USER_EMAIL, USER_PASSWORD


class Credentials(BaseModel):
    username: str
    password: str


class FakeCredentials(BaseModel):
    name: str
    pwd: str


class WrongTypesCredentials(BaseModel):
    username: int
    password: dict


FAKE_CREDENTIALS_CASES = [
    {
        "id": "wrong_field_names",
        "credentials": FakeCredentials(
            name=USER_EMAIL,
            pwd=USER_PASSWORD
        ),
    },
    {
        "id": "empty_values",
        "credentials": Credentials(
            username="",
            password=""
        ),
    },
    {
        "id": "wrong_type_values",
        "credentials": WrongTypesCredentials(
            username=1,
            password={"Bat": "Man"}
        ),
    },
    {
        "id": "incorrect_email_value",
        "credentials": Credentials(
            username="notemaildotcom",
            password=USER_PASSWORD
        ),
    },
    {
        "id": "incorrect_password_value",
        "credentials": Credentials(
            username=USER_EMAIL,
            password="incorrectpassword"
        ),
    },
]


def test_check_credentials_success():
    credentials = Credentials(
        username=USER_EMAIL,
        password=USER_PASSWORD
    )

    user: UserAuth = get_and_check_credentials(credentials=credentials)
    assert user is not None
    assert isinstance(user, UserAuth)
    assert user.email == USER_EMAIL
    assert user.password.get_secret_value() == USER_PASSWORD

def test_check_credentials_failed_with_fake_credentials_object():
    fake_credentials_objects = [
        "",
        1,
        ["abra", "kadabra"],
        {"Bat": "Man"},
        TypeError,
    ]
    for obj in fake_credentials_objects:
        with pytest.raises(InvalidCredentialsHTTPException) as exc:
            user: UserAuth = get_and_check_credentials(credentials=obj)
        assert exc.errisinstance(InvalidCredentialsHTTPException)

@pytest.mark.parametrize(
    "case",
    FAKE_CREDENTIALS_CASES,
    ids=lambda c: c["id"]
)
def test_check_credentials_failed(case):
    credentials = case["credentials"]
    with pytest.raises(InvalidCredentialsHTTPException) as exc:
        user: UserAuth = get_and_check_credentials(credentials=credentials)
    assert exc.errisinstance(InvalidCredentialsHTTPException)

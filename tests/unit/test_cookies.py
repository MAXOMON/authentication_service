from unittest.mock import MagicMock

from app.config import settings
from app.utils import set_token_cookies



def test_set_token_cookies():
    mock_response = MagicMock()
    access = "access_token"
    refresh = "refresh_token"
    set_token_cookies(mock_response, access, refresh)
    mock_response.set_cookie.assert_called()
    mock_response.set_cookie.assert_called_with(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRES_MINUTES * 60,
        domain=settings.SESSION_COOKIE_DOMAIN,
        path="/",
    )
    assert mock_response.set_cookie.call_count == 2

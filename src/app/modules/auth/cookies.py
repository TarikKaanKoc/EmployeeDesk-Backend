"""HttpOnly auth cookies for the web client; tokens never reach JS."""

from fastapi import Response

from src.app.core.config import settings
from src.app.modules.auth.tokens import ACCESS_COOKIE, REFRESH_COOKIE, SESSION_COOKIE


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = not settings.DEBUG
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/auth",
    )
    response.set_cookie(
        SESSION_COOKIE,
        "1",
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    response.delete_cookie(SESSION_COOKIE, path="/")

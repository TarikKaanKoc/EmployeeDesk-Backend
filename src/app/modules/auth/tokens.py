"""Every JWT this API mints or reads goes through here.

`sub` is the identity's `sign_in_subject`, never the employee id: the
employee is resolved from the `identities` table on every request, so a
deactivated employee is refused the moment the row says so, token or not.
"""

import uuid
from datetime import timedelta
from enum import StrEnum
from typing import Any, Dict, Optional

import jwt
from fastapi import Request
from loguru import logger

from src.app.core.clock import utcnow
from src.app.core.config import settings
from src.app.modules.auth.revocation import is_revoked

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
SESSION_COOKIE = "has_session"


class Kind(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


_AUDIENCE = {Kind.ACCESS: "employeedesk:access", Kind.REFRESH: "employeedesk:refresh"}


def _ttl(kind: Kind) -> timedelta:
    if kind is Kind.ACCESS:
        return timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    return timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)


def issue(kind: Kind, subject: str, *, extra: Optional[Dict[str, Any]] = None) -> str:
    now = utcnow()
    claims: Dict[str, Any] = {
        "sub": subject,
        "type": kind.value,
        "aud": _AUDIENCE[kind],
        "iat": now,
        "exp": now + _ttl(kind),
        "jti": uuid.uuid4().hex,
        **(extra or {}),
    }
    return jwt.encode(claims, settings.signing_key(), algorithm=settings.JWT_ALGORITHM)


def decode(token: str, kind: Kind) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.signing_key(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=_AUDIENCE[kind],
        )
    except jwt.ExpiredSignatureError:
        logger.debug(f"{kind.value} token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid {kind.value} token: {e}")
        return None
    if payload.get("type") != kind.value:
        return None
    return payload


async def verify(token: str, kind: Kind) -> Optional[Dict[str, Any]]:
    payload = decode(token, kind)
    if payload is None or await is_revoked(payload):
        return None
    return payload


def bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    return auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else None


def extract_token(
    request: Request, kind: Kind, *, body_token: Optional[str] = None
) -> Optional[str]:
    """Body first (API clients send the refresh token there), then the
    HttpOnly cookie (web), then the Authorization header."""
    if body_token:
        return body_token
    name = ACCESS_COOKIE if kind is Kind.ACCESS else REFRESH_COOKIE
    if request.cookies.get(name):
        return request.cookies.get(name)
    return bearer(request)

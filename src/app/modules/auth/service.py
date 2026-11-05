"""Login, refresh rotation, logout.

An identity whose employee is inactive cannot sign in and, if it already
holds a token, is refused on the next request (see `api/dependencies`).
Wrong email and wrong password answer identically so the login form
cannot be used to enumerate the directory.
"""

from typing import Any, Dict, Optional

from src.app.core.exceptions import Unauthorized
from src.app.database.enums import EmploymentStatus
from src.app.database.repository_provider import RepositoryProvider
from src.app.modules.auth import revocation, tokens
from src.app.modules.auth.schemas import TokenPair
from src.app.modules.auth.security import verify_password

#: Verified against when the identity has no password, so a missing
#: account costs the same time as a wrong password.
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _pair(subject: str) -> TokenPair:
    return TokenPair(
        accessToken=tokens.issue(tokens.Kind.ACCESS, subject),
        refreshToken=tokens.issue(tokens.Kind.REFRESH, subject),
    )


async def login(repos: RepositoryProvider, email: str, password: str) -> TokenPair:
    identity = await repos.identities.by_email(email)
    hashed = (
        identity.password_hash if identity and identity.password_hash else _DUMMY_HASH
    )
    ok = await verify_password(password, hashed)
    if not identity or not identity.password_hash or not ok:
        raise Unauthorized("Invalid email or password.", code="INVALID_CREDENTIALS")
    if identity.employee.employment_status is not EmploymentStatus.active:
        raise Unauthorized("This account is not active.", code="ACCOUNT_INACTIVE")
    return _pair(identity.sign_in_subject)


async def refresh(repos: RepositoryProvider, payload: Dict[str, Any]) -> TokenPair:
    """Rotate: spend the old refresh token, issue a new pair. A spent
    token presented again is refused (and, past the grace window, revokes
    every session of that subject)."""
    subject = payload.get("sub")
    identity = await repos.identities.by_subject(subject) if subject else None
    if (
        not identity
        or identity.employee.employment_status is not EmploymentStatus.active
    ):
        raise Unauthorized("Session is no longer valid.", code="SESSION_INVALID")
    if not await revocation.consume_refresh(payload):
        raise Unauthorized("Refresh token already used.", code="REFRESH_REUSED")
    return _pair(subject)


async def logout(
    access_payload: Optional[Dict[str, Any]], refresh_payload: Optional[Dict[str, Any]]
) -> None:
    for payload in (access_payload, refresh_payload):
        if payload:
            await revocation.revoke_token(payload)

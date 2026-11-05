"""Who is calling.

`get_current_employee` is the only way a route learns the caller. It reads
the access token (HttpOnly cookie for the web, Bearer for API clients),
looks the subject up in `identities`, and refuses if the employee is not
active. Everything downstream filters by `current.employee_id`; no route
or tool accepts an employee id from the client.
"""

from dataclasses import dataclass
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.app.core import rate_limiter
from src.app.database.enums import EmploymentStatus
from src.app.database.models import Employee
from src.app.database.repository_provider import RepositoryProvider, get_repos
from src.app.modules.auth import tokens

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentEmployee:
    employee_id: str
    subject: str
    employee: Employee


async def _verify_access_once(request: Request, token: str) -> Optional[Dict[str, Any]]:
    """Verified once per request and shared between the rate limiter and the
    endpoint through `request.state`; nothing outlives the request."""
    cached = getattr(request.state, "_access_payload", None)
    if cached is not None and cached[0] == token:
        return cached[1]
    payload = await tokens.verify(token, tokens.Kind.ACCESS)
    request.state._access_payload = (token, payload)
    return payload


async def _identify_for_rate_limit(request: Request) -> Optional[str]:
    token = tokens.extract_token(request, tokens.Kind.ACCESS)
    if not token:
        return None
    payload = await _verify_access_once(request, token)
    return payload.get("sub") if payload else None


rate_limiter.set_identity_resolver(_identify_for_rate_limit)


async def verify_access_token(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)
    ] = None,
) -> Dict[str, Any]:
    token = tokens.extract_token(request, tokens.Kind.ACCESS)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = await _verify_access_once(request, token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid access token")
    return payload


async def get_current_employee(
    payload: Annotated[Dict[str, Any], Depends(verify_access_token)],
    repos: Annotated[RepositoryProvider, Depends(get_repos)],
) -> CurrentEmployee:
    identity = await repos.identities.by_subject(payload["sub"])
    if identity is None:
        raise HTTPException(status_code=401, detail="Unknown identity")
    if identity.employee.employment_status is not EmploymentStatus.active:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ACCOUNT_INACTIVE",
                "message": "This account is not active.",
            },
        )
    return CurrentEmployee(
        employee_id=identity.employee_id,
        subject=identity.sign_in_subject,
        employee=identity.employee,
    )


async def verify_refresh_token(
    request: Request, body_token: Optional[str] = None
) -> Dict[str, Any]:
    token = tokens.extract_token(request, tokens.Kind.REFRESH, body_token=body_token)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    payload = await tokens.verify(token, tokens.Kind.REFRESH)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return payload

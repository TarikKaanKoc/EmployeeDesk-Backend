from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, Response, status

from src.app.api.dependencies import (
    CurrentEmployee,
    get_current_employee,
    verify_refresh_token,
)
from src.app.core.rate_limiter import rate_limit
from src.app.database.repository_provider import RepositoryProvider, get_repos
from src.app.modules.auth import service, tokens
from src.app.modules.auth.cookies import clear_auth_cookies, set_auth_cookies
from src.app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenPair
from src.app.modules.employees.schemas import EmployeeMe

router = APIRouter()


@router.post("/login", response_model=TokenPair, dependencies=[rate_limit(10, 60)])
async def login(
    body: LoginRequest,
    response: Response,
    repos: Annotated[RepositoryProvider, Depends(get_repos)],
) -> TokenPair:
    pair = await service.login(repos, body.email, body.password)
    set_auth_cookies(response, pair.accessToken, pair.refreshToken)
    return pair


@router.post("/refresh", response_model=TokenPair, dependencies=[rate_limit(30, 60)])
async def refresh(
    request: Request,
    response: Response,
    repos: Annotated[RepositoryProvider, Depends(get_repos)],
    body: Optional[RefreshRequest] = None,
) -> TokenPair:
    payload = await verify_refresh_token(request, body.refreshToken if body else None)
    pair = await service.refresh(repos, payload)
    set_auth_cookies(response, pair.accessToken, pair.refreshToken)
    return pair


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[rate_limit(30, 60)]
)
async def logout(request: Request, response: Response) -> Response:
    access = tokens.extract_token(request, tokens.Kind.ACCESS)
    refresh_token = tokens.extract_token(request, tokens.Kind.REFRESH)
    await service.logout(
        tokens.decode(access, tokens.Kind.ACCESS) if access else None,
        tokens.decode(refresh_token, tokens.Kind.REFRESH) if refresh_token else None,
    )
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=EmployeeMe, dependencies=[rate_limit(60, 60)])
async def me(
    current: Annotated[CurrentEmployee, Depends(get_current_employee)],
) -> EmployeeMe:
    return EmployeeMe.from_row(current.employee)

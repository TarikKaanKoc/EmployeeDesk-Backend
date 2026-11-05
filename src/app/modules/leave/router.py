from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.app.api.dependencies import CurrentEmployee, get_current_employee
from src.app.core.rate_limiter import rate_limit
from src.app.database.repository_provider import RepositoryProvider, get_repos
from src.app.modules.leave import service
from src.app.modules.leave.schemas import (
    LeaveBalanceOut,
    LeaveBalancesOut,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveRequestsOut,
)

router = APIRouter()

Current = Annotated[CurrentEmployee, Depends(get_current_employee)]
Repos = Annotated[RepositoryProvider, Depends(get_repos)]


@router.get(
    "/balances", response_model=LeaveBalancesOut, dependencies=[rate_limit(60, 60)]
)
async def get_balances(current: Current, repos: Repos) -> LeaveBalancesOut:
    rows = await service.balances(repos, current)
    return LeaveBalancesOut(
        employeeId=current.employee_id,
        balances=[LeaveBalanceOut.from_row(r) for r in rows],
    )


@router.get(
    "/requests", response_model=LeaveRequestsOut, dependencies=[rate_limit(60, 60)]
)
async def list_requests(current: Current, repos: Repos) -> LeaveRequestsOut:
    rows = await service.requests(repos, current)
    return LeaveRequestsOut(
        employeeId=current.employee_id,
        requests=[LeaveRequestOut.from_row(r) for r in rows],
    )


@router.get(
    "/requests/{request_id}",
    response_model=LeaveRequestOut,
    dependencies=[rate_limit(60, 60)],
)
async def get_request(
    request_id: str, current: Current, repos: Repos
) -> LeaveRequestOut:
    return LeaveRequestOut.from_row(await service.request(repos, current, request_id))


@router.post(
    "/requests",
    response_model=LeaveRequestOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit(10, 60)],
)
async def create_request(
    body: LeaveRequestCreate, current: Current, repos: Repos
) -> LeaveRequestOut:
    """A direct submission by the signed-in person is its own confirmation;
    the assistant's path records the explicit confirm step separately."""
    row = await service.submit(repos, current, body, confirmation_recorded=True)
    return LeaveRequestOut.from_row(row)

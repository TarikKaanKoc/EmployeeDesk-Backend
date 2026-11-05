"""Leave balances and requests for one employee: the caller.

Submitting a request is the only write in this module. It runs in the
request's transaction: the balance row is locked, the request inserted,
`pending_days` raised; `available_days` follows because it is a generated
column. The assistant never calls `submit` directly - it goes through the
confirmation gate, which calls it only after the person said yes.
"""

from datetime import date
from typing import List

from src.app.api.dependencies import CurrentEmployee
from src.app.core.exceptions import Conflict, Invalid, NotFound
from src.app.database.enums import LeaveRequestStatus
from src.app.database.models import LeaveBalance, LeaveRequest
from src.app.database.repository_provider import RepositoryProvider
from src.app.modules.employees.scope import own
from src.app.modules.leave.schemas import LeaveRequestCreate


async def balances(
    repos: RepositoryProvider, current: CurrentEmployee
) -> List[LeaveBalance]:
    return await repos.leave.balances(own(current, current.employee_id))


async def requests(
    repos: RepositoryProvider, current: CurrentEmployee
) -> List[LeaveRequest]:
    return await repos.leave.requests(own(current, current.employee_id))


async def request(
    repos: RepositoryProvider, current: CurrentEmployee, request_id: str
) -> LeaveRequest:
    """404, not 403, for someone else's id: the row's existence is not the
    caller's to learn."""
    row = await repos.leave.request(own(current, current.employee_id), request_id)
    if row is None:
        raise NotFound("Leave request not found.", code="LEAVE_REQUEST_NOT_FOUND")
    return row


def _days(start: date, end: date) -> int:
    return (end - start).days + 1


async def validate(
    repos: RepositoryProvider, current: CurrentEmployee, body: LeaveRequestCreate
) -> LeaveBalance:
    """Everything that can refuse a request, without writing. Shared by
    `submit` and by the assistant's draft step, so what the person is
    asked to confirm is a request that will succeed."""
    employee_id = own(current, current.employee_id)
    balance = await repos.leave.balance(employee_id, body.leaveType)
    if balance is None:
        raise Invalid("No balance for this leave type.", code="NO_BALANCE")
    days = _days(body.startDate, body.endDate)
    if balance.available_days < days:
        raise Invalid(
            f"Insufficient balance: {days} days requested, {balance.available_days} available.",
            code="INSUFFICIENT_BALANCE",
            extra={"requested": days, "available": float(balance.available_days)},
        )
    clash = await repos.leave.overlapping(employee_id, body.startDate, body.endDate)
    if clash:
        raise Conflict(
            "Overlaps an existing pending or approved request.",
            code="OVERLAPPING_REQUEST",
            errors=[c.id for c in clash],
        )
    return balance


async def submit(
    repos: RepositoryProvider,
    current: CurrentEmployee,
    body: LeaveRequestCreate,
    *,
    confirmation_recorded: bool,
) -> LeaveRequest:
    await validate(repos, current, body)
    employee_id = current.employee_id
    balance = await repos.leave.balance(employee_id, body.leaveType, for_update=True)
    days = _days(body.startDate, body.endDate)
    if balance.available_days < days:
        raise Invalid("Insufficient balance.", code="INSUFFICIENT_BALANCE")
    row = LeaveRequest(
        id=await repos.leave.next_request_id(),
        employee_id=employee_id,
        leave_type=body.leaveType,
        start_date=body.startDate,
        end_date=body.endDate,
        reason_category=body.reasonCategory,
        status=LeaveRequestStatus.pending,
        confirmation_recorded=confirmation_recorded,
    )
    await repos.leave.add(row)
    balance.pending_days = balance.pending_days + days
    await repos.session.flush()
    await repos.session.refresh(row)
    return row

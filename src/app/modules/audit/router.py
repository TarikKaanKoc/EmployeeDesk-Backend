from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from src.app.api.dependencies import CurrentEmployee, get_current_employee
from src.app.core.rate_limiter import rate_limit
from src.app.database.repository_provider import RepositoryProvider, get_repos
from src.app.modules.audit.schemas import AuditEventOut, AuditPage

router = APIRouter()


@router.get("/me", response_model=AuditPage, dependencies=[rate_limit(60, 60)])
async def my_trail(
    current: Annotated[CurrentEmployee, Depends(get_current_employee)],
    repos: Annotated[RepositoryProvider, Depends(get_repos)],
    limit: int = Query(default=50, ge=1, le=200),
    before: Optional[int] = Query(default=None),
) -> AuditPage:
    rows = await repos.audit.for_employee(
        current.employee_id, limit=limit, before_id=before
    )
    return AuditPage(
        employeeId=current.employee_id,
        events=[AuditEventOut.from_row(r) for r in rows],
        nextBefore=rows[-1].id if len(rows) == limit else None,
    )

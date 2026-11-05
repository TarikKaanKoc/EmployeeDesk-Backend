from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.api.dependencies import CurrentEmployee, get_current_employee
from src.app.core.rate_limiter import rate_limit
from src.app.modules.employees import service
from src.app.modules.employees.schemas import EmployeeMe

router = APIRouter()


@router.get("/me", response_model=EmployeeMe, dependencies=[rate_limit(60, 60)])
async def get_me(
    current: Annotated[CurrentEmployee, Depends(get_current_employee)],
) -> EmployeeMe:
    """The caller's own record. Deliberately no `/employees/{id}` and no
    listing: the directory is not browsable."""
    return EmployeeMe.from_row(await service.me(current))

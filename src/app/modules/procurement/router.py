from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.api.dependencies import CurrentEmployee, get_current_employee
from src.app.core.rate_limiter import rate_limit
from src.app.modules.procurement import service
from src.app.modules.procurement.schemas import PurchaseRequestOut, PurchaseRequestsOut

router = APIRouter()

Current = Annotated[CurrentEmployee, Depends(get_current_employee)]


@router.get(
    "/requests", response_model=PurchaseRequestsOut, dependencies=[rate_limit(60, 60)]
)
async def list_requests(current: Current) -> PurchaseRequestsOut:
    return PurchaseRequestsOut(
        employeeId=current.employee_id, requests=await service.list_requests(current)
    )


@router.get(
    "/requests/{pr_number}",
    response_model=PurchaseRequestOut,
    dependencies=[rate_limit(60, 60)],
)
async def get_request(pr_number: str, current: Current) -> PurchaseRequestOut:
    return await service.get_request(current, pr_number)

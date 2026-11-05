"""Purchase request status for the caller's own requests.

The ERP answers for any PR number; the scope check happens here, after
the fetch and before anything is returned. A PR that exists but belongs
to someone else is a 404 for this caller.
"""

from typing import List

from src.app.api.dependencies import CurrentEmployee
from src.app.core.exceptions import NotFound
from src.app.modules.employees.scope import own
from src.app.modules.procurement import erp_client
from src.app.modules.procurement.schemas import PurchaseRequestOut


def _out(raw: dict) -> PurchaseRequestOut:
    return PurchaseRequestOut(
        prNumber=raw["pr_number"],
        requesterEmployeeId=raw["requester_employee_id"],
        department=raw["department"],
        businessPurpose=raw["business_purpose"],
        amountQar=raw["amount_qar"],
        status=raw["status"],
        currentStep=raw["current_step"],
        createdDate=raw["created_date"],
        lastUpdated=raw["last_updated"],
        reference=raw["mock_reference"],
    )


async def list_requests(current: CurrentEmployee) -> List[PurchaseRequestOut]:
    employee_id = own(current, current.employee_id)
    rows = await erp_client.list_for_requester(employee_id)
    return [_out(r) for r in rows if r["requester_employee_id"] == employee_id]


async def get_request(current: CurrentEmployee, pr_number: str) -> PurchaseRequestOut:
    employee_id = own(current, current.employee_id)
    raw = await erp_client.get(pr_number.strip().upper())
    if raw is None or raw["requester_employee_id"] != employee_id:
        raise NotFound("Purchase request not found.", code="PURCHASE_REQUEST_NOT_FOUND")
    return _out(raw)

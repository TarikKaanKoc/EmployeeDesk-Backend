"""The mock ERP's wire contract. Snake-case on purpose: it is "another
system", and the API's procurement module maps it to its own shapes."""

from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel

from src.app.database.enums import PurchaseRequestStatus
from src.app.database.models import PurchaseRequest


class PurchaseRequestRecord(BaseModel):
    pr_number: str
    requester_employee_id: str
    department: str
    business_purpose: str
    amount_qar: Decimal
    status: PurchaseRequestStatus
    current_step: str
    created_date: date
    last_updated: date
    mock_reference: str

    @classmethod
    def from_row(cls, r: PurchaseRequest) -> "PurchaseRequestRecord":
        return cls(
            pr_number=r.pr_number,
            requester_employee_id=r.requester_employee_id,
            department=r.department,
            business_purpose=r.business_purpose,
            amount_qar=r.amount_qar,
            status=r.status,
            current_step=r.current_step,
            created_date=r.created_date,
            last_updated=r.last_updated,
            mock_reference=r.mock_reference,
        )


class PurchaseRequestList(BaseModel):
    items: List[PurchaseRequestRecord]
    total: int

from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel

from src.app.database.enums import PurchaseRequestStatus


class PurchaseRequestOut(BaseModel):
    """What the mock ERP returns, as the API shows it. Field names are the
    ERP's contract (see `src/mock_erp`)."""

    prNumber: str
    requesterEmployeeId: str
    department: str
    businessPurpose: str
    amountQar: Decimal
    status: PurchaseRequestStatus
    currentStep: str
    createdDate: date
    lastUpdated: date
    reference: str


class PurchaseRequestsOut(BaseModel):
    employeeId: str
    requests: List[PurchaseRequestOut]

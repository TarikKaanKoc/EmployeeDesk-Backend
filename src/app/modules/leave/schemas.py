from datetime import date, datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field, model_validator

from src.app.database.enums import LeaveReasonCategory, LeaveRequestStatus, LeaveType
from src.app.database.models import LeaveBalance, LeaveRequest


class LeaveBalanceOut(BaseModel):
    leaveType: LeaveType
    entitledDays: Decimal
    usedDays: Decimal
    pendingDays: Decimal
    availableDays: Decimal
    asOfDate: date

    @classmethod
    def from_row(cls, b: LeaveBalance) -> "LeaveBalanceOut":
        return cls(
            leaveType=b.leave_type,
            entitledDays=b.entitled_days,
            usedDays=b.used_days,
            pendingDays=b.pending_days,
            availableDays=b.available_days,
            asOfDate=b.as_of_date,
        )


class LeaveBalancesOut(BaseModel):
    employeeId: str
    balances: List[LeaveBalanceOut]


class LeaveRequestCreate(BaseModel):
    leaveType: LeaveType
    startDate: date
    endDate: date
    reasonCategory: LeaveReasonCategory = LeaveReasonCategory.personal

    @model_validator(mode="after")
    def _dates(self) -> "LeaveRequestCreate":
        if self.endDate < self.startDate:
            raise ValueError("endDate must be on or after startDate")
        if (self.endDate - self.startDate).days + 1 > 60:
            raise ValueError("a single request may not exceed 60 days")
        return self


class LeaveRequestOut(BaseModel):
    requestId: str
    employeeId: str
    leaveType: LeaveType
    startDate: date
    endDate: date
    days: int
    reasonCategory: LeaveReasonCategory
    status: LeaveRequestStatus
    confirmationRecorded: bool
    createdAt: datetime

    @classmethod
    def from_row(cls, r: LeaveRequest) -> "LeaveRequestOut":
        return cls(
            requestId=r.id,
            employeeId=r.employee_id,
            leaveType=r.leave_type,
            startDate=r.start_date,
            endDate=r.end_date,
            days=r.days,
            reasonCategory=r.reason_category,
            status=r.status,
            confirmationRecorded=r.confirmation_recorded,
            createdAt=r.created_at,
        )


class LeaveRequestsOut(BaseModel):
    employeeId: str
    requests: List[LeaveRequestOut] = Field(default_factory=list)

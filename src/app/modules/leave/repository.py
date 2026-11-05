"""Every query here takes `employee_id`; there is no method that reads
across employees."""

from datetime import date
from typing import List, Optional

from sqlalchemy import func, select, text

from src.app.database.base_repository import BaseRepository
from src.app.database.enums import LeaveRequestStatus, LeaveType
from src.app.database.models import LeaveBalance, LeaveRequest


class LeaveRepository(BaseRepository[LeaveRequest]):
    model = LeaveRequest

    async def balances(self, employee_id: str) -> List[LeaveBalance]:
        result = await self.session.execute(
            select(LeaveBalance)
            .where(LeaveBalance.employee_id == employee_id)
            .order_by(LeaveBalance.leave_type)
        )
        return list(result.scalars())

    async def balance(
        self, employee_id: str, leave_type: LeaveType, *, for_update: bool = False
    ) -> Optional[LeaveBalance]:
        stmt = select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type == leave_type,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def requests(self, employee_id: str) -> List[LeaveRequest]:
        result = await self.session.execute(
            select(LeaveRequest)
            .where(LeaveRequest.employee_id == employee_id)
            .order_by(LeaveRequest.start_date.desc())
        )
        return list(result.scalars())

    async def request(
        self, employee_id: str, request_id: str
    ) -> Optional[LeaveRequest]:
        return await self.one_or_none(
            LeaveRequest.employee_id == employee_id, LeaveRequest.id == request_id
        )

    async def overlapping(
        self, employee_id: str, start: date, end: date
    ) -> List[LeaveRequest]:
        result = await self.session.execute(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_(
                    [LeaveRequestStatus.pending, LeaveRequestStatus.approved]
                ),
                LeaveRequest.start_date <= end,
                LeaveRequest.end_date >= start,
            )
        )
        return list(result.scalars())

    async def next_request_id(self) -> str:
        n = (
            await self.session.execute(text("SELECT nextval('leave_request_seq')"))
        ).scalar_one()
        return f"LR-{n}"

    async def count(self, employee_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(LeaveRequest)
                .where(LeaveRequest.employee_id == employee_id)
            )
        ).scalar_one()

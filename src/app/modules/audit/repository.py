from typing import List

from sqlalchemy import select

from src.app.database.base_repository import BaseRepository
from src.app.database.models import AuditEvent


class AuditRepository(BaseRepository[AuditEvent]):
    model = AuditEvent

    async def for_employee(
        self, employee_id: str, *, limit: int, before_id: int | None
    ) -> List[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.employee_id == employee_id)
        if before_id is not None:
            stmt = stmt.where(AuditEvent.id < before_id)
        stmt = stmt.order_by(AuditEvent.id.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

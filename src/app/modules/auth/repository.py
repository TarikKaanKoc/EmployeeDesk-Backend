from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.app.database.base_repository import BaseRepository
from src.app.database.models import Employee, Identity


class IdentityRepository(BaseRepository[Identity]):
    model = Identity

    async def by_subject(self, subject: str) -> Optional[Identity]:
        result = await self.session.execute(
            select(Identity)
            .options(joinedload(Identity.employee))
            .where(Identity.sign_in_subject == subject)
        )
        return result.scalar_one_or_none()

    async def by_email(self, email: str) -> Optional[Identity]:
        result = await self.session.execute(
            select(Identity)
            .join(Identity.employee)
            .options(joinedload(Identity.employee))
            .where(Employee.email_alias == email.strip().lower())
        )
        return result.scalar_one_or_none()

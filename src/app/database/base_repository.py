"""Session-scoped repository base. A repository is created per request
with the request's session; it never opens or commits one itself."""

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.models import Base

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    model: Type[M]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key) -> Optional[M]:
        return await self.session.get(self.model, key)

    async def add(self, row: M) -> M:
        self.session.add(row)
        await self.session.flush()
        return row

    async def one_or_none(self, *where) -> Optional[M]:
        result = await self.session.execute(select(self.model).where(*where))
        return result.scalar_one_or_none()

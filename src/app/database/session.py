"""`get_session` - one session (and one transaction) per request."""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.connections import get_session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        async with session.begin():
            yield session

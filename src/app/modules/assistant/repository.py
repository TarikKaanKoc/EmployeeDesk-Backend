from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.app.database.base_repository import BaseRepository
from src.app.database.models import Conversation, Message, UntrustedDocument


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def owned(
        self, employee_id: str, conversation_id: str
    ) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.employee_id == employee_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, employee_id: str, *, limit: int = 50) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.employee_id == employee_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def add_message(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        return message


class UntrustedDocumentRepository(BaseRepository[UntrustedDocument]):
    model = UntrustedDocument

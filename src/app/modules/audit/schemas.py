from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.app.database.enums import AuditEventType
from src.app.database.models import AuditEvent


class AuditEventOut(BaseModel):
    id: int
    eventType: AuditEventType
    conversationId: Optional[str]
    payload: Dict[str, Any]
    createdAt: datetime

    @classmethod
    def from_row(cls, e: AuditEvent) -> "AuditEventOut":
        return cls(
            id=e.id,
            eventType=e.event_type,
            conversationId=e.conversation_id,
            payload=e.payload,
            createdAt=e.created_at,
        )


class AuditPage(BaseModel):
    employeeId: str
    events: List[AuditEventOut]
    nextBefore: Optional[int]

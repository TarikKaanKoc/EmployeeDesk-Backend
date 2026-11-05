"""Append-only trail. `record` never raises into the caller's flow."""

from typing import Any, Dict, Optional

from loguru import logger

from src.app.database.enums import AuditEventType
from src.app.database.models import AuditEvent
from src.app.database.repository_provider import RepositoryProvider


async def record(
    repos: RepositoryProvider,
    employee_id: str,
    event_type: AuditEventType,
    payload: Optional[Dict[str, Any]] = None,
    *,
    conversation_id: Optional[str] = None,
) -> None:
    try:
        await repos.audit.add(
            AuditEvent(
                employee_id=employee_id,
                event_type=event_type,
                conversation_id=conversation_id,
                payload=payload or {},
            )
        )
    except Exception as e:  # noqa: BLE001 - the trail must not break the turn
        logger.error(f"audit record failed: {e}")

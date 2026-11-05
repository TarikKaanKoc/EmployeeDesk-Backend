"""The write gate.

A write tool never writes. It validates, then parks a `PendingAction` in
Redis under the employee's id with a short TTL and returns an action id.
The write happens only when `POST /assistant/confirm/{id}` arrives from
the same employee. Typing "yes" into the chat does not count: the model
cannot confirm on the person's behalf, because confirming is not a tool.
"""

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

from src.app.core.clock import utcnow
from src.app.core.redis import get_redis

TTL = timedelta(minutes=10)


@dataclass
class PendingAction:
    action_id: str
    employee_id: str
    conversation_id: Optional[str]
    kind: str
    payload: Dict[str, Any]
    summary: str
    expires_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def _key(employee_id: str, action_id: str) -> str:
    return f"assistant:pending:{employee_id}:{action_id}"


async def park(
    employee_id: str,
    *,
    conversation_id: Optional[str],
    kind: str,
    payload: Dict[str, Any],
    summary: str,
) -> PendingAction:
    action = PendingAction(
        action_id=secrets.token_urlsafe(12),
        employee_id=employee_id,
        conversation_id=conversation_id,
        kind=kind,
        payload=payload,
        summary=summary,
        expires_at=(utcnow() + TTL).isoformat(),
    )
    redis = await get_redis()
    await redis.set(
        _key(employee_id, action.action_id),
        action.to_json(),
        ex=int(TTL.total_seconds()),
    )
    return action


async def take(employee_id: str, action_id: str) -> Optional[PendingAction]:
    """Fetch and delete in one step, so an action can be confirmed once.
    The key is scoped by employee: another employee's id finds nothing."""
    redis = await get_redis()
    key = _key(employee_id, action_id)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.get(key)
        pipe.delete(key)
        raw, _ = await pipe.execute()
    if not raw:
        return None
    return PendingAction(**json.loads(raw))

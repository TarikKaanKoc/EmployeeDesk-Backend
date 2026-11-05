"""Server-sent events for a turn: `meta`, `token`, `tool_call`, `done`,
`error`. One JSON object per event."""

import json
from typing import Any, AsyncIterator, Dict

from src.app.modules.assistant.agent import TurnEvent


def encode(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def sse(events: AsyncIterator[TurnEvent]) -> AsyncIterator[str]:
    async for ev in events:
        if ev.kind == "token":
            yield encode("token", {"text": ev.text})
        elif ev.kind in ("tool_start", "tool_call"):
            yield encode(ev.kind, ev.tool or {})
        elif ev.kind in ("meta", "done"):
            yield encode(ev.kind, ev.data)

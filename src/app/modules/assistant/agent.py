"""The tool loop.

Streams the model; when the stream ends in tool calls, runs each through
`tools.run`, appends the results, and streams again. Bounded rounds.
Everything observable about a turn (tokens, tool calls and their status,
citations, a pending action) is yielded as `TurnEvent`s so the SSE wire
and the JSON response are built from the same sequence.
"""

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from loguru import logger

from src.app.core import llm
from src.app.modules.assistant import tools
from src.app.modules.assistant.tools import ToolContext

MAX_ROUNDS = 4


@dataclass
class TurnEvent:
    kind: str  # token | tool_start | tool_call | done
    text: str = ""
    tool: Optional[Dict[str, Any]] = None
    data: Dict[str, Any] = field(default_factory=dict)


def _status_of(result: Dict[str, Any]) -> str:
    if result.get("error") == "OWN_RECORDS_ONLY":
        return "refused"
    if result.get("error"):
        return "error"
    if result.get("status") == "confirmation_required":
        return "confirmation_required"
    if "clauses" in result and not result["clauses"]:
        return "empty"
    return "ok"


async def run_turn(
    ctx: ToolContext, messages: List[Dict[str, Any]]
) -> AsyncIterator[TurnEvent]:
    """Yields events; the last one is `done` with the assistant's full text
    and the tool call log in `data`."""
    text_parts: List[str] = []
    log: List[Dict[str, Any]] = []
    for _ in range(MAX_ROUNDS):
        calls: List[llm.ToolCall] = []
        async for ev in llm.stream(messages, tools=tools.SPECS):
            if ev.kind == "text":
                text_parts.append(ev.text)
                yield TurnEvent("token", text=ev.text)
            elif ev.kind == "calls":
                calls = ev.calls
        if not calls:
            break
        messages.append(
            {
                "role": "assistant",
                "content": "".join(text_parts) or None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.arguments or "{}"},
                    }
                    for c in calls
                ],
            }
        )
        text_parts.clear()
        for call in calls:
            # Announced before it runs, so the screen can say what is being
            # looked up instead of "thinking" while the ERP or the DB answers.
            yield TurnEvent("tool_start", tool={"name": call.name})
            result = await tools.run(ctx, call.name, call.arguments)
            status = _status_of(result)
            entry = {
                "name": call.name,
                "status": status,
                "arguments": tools.parse_args(call.arguments),
                "detail": result.get("message")
                or result.get("summary")
                or result.get("note")
                or None,
                # The screen draws the data itself (a balance card, a request
                # table), so the result travels with the event; refusals and
                # errors carry only their message.
                "result": result
                if status in ("ok", "confirmation_required", "empty")
                else None,
            }
            log.append(entry)
            logger.info(f"tool {call.name} -> {status}")
            yield TurnEvent("tool_call", tool=entry)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    else:
        logger.warning("tool loop hit MAX_ROUNDS")
    yield TurnEvent("done", text="".join(text_parts), data={"tool_calls": log})

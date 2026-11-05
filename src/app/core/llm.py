"""The one door to the language model.

Azure AI Foundry's OpenAI-compatible project endpoint, through the plain
OpenAI SDK with `base_url`. One client per process. `embed` returns None
when nothing is configured so retrieval falls back to keyword search; chat
callers (the assistant) check `settings.llm_configured` themselves.
"""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from loguru import logger
from openai import APIError, AsyncOpenAI

from src.app.core.config import settings
from src.app.core.exceptions import UpstreamFailed

_client: Optional[AsyncOpenAI] = None

_REASONING_PREFIXES = ("gpt-5", "gpt-6", "o1", "o3", "o4")


def supports_reasoning(model: str) -> bool:
    return model.lower().startswith(_REASONING_PREFIXES)


def reasoning_kwargs(model: Optional[str] = None) -> Dict[str, Any]:
    """`reasoning_effort` only for models that understand it; Azure answers
    400 to the others."""
    model = model or settings.AZURE_OPENAI_CHAT_DEPLOYMENT
    if settings.AZURE_OPENAI_REASONING_EFFORT and supports_reasoning(model):
        return {"reasoning_effort": settings.AZURE_OPENAI_REASONING_EFFORT}
    return {}


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.llm_configured:
            raise RuntimeError(
                "AZURE_OPENAI_BASE_URL / AZURE_OPENAI_API_KEY are not set"
            )
        _client = AsyncOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            base_url=settings.AZURE_OPENAI_BASE_URL,
            default_headers={"api-key": settings.AZURE_OPENAI_API_KEY},
            timeout=60,
            max_retries=2,
        )
    return _client


async def embed(texts: List[str]) -> Optional[List[List[float]]]:
    if not settings.embeddings_configured or not texts:
        return None
    try:
        resp = await client().embeddings.create(
            model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            input=texts,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
    except Exception as e:  # noqa: BLE001 - retrieval must still answer by keyword
        logger.warning(f"Embedding call failed, keyword search only: {e}")
        return None
    return [item.embedding for item in resp.data]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""


@dataclass
class Reply:
    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    tokens: Dict[str, int] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return (self.content or "").strip()


@dataclass
class StreamEvent:
    """`text` carries a piece of the answer; `calls` arrives last with every
    tool call the stream assembled; `done` closes with the finish reason."""

    kind: str
    text: str = ""
    calls: List[ToolCall] = field(default_factory=list)


def _calls_of(message: Any) -> List[ToolCall]:
    return [
        ToolCall(
            id=c.id or "",
            name=c.function.name or "",
            arguments=c.function.arguments or "",
        )
        for c in (getattr(message, "tool_calls", None) or [])
    ]


async def complete(
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 1200,
    tool_choice: Optional[str] = None,
) -> Reply:
    extra: Dict[str, Any] = {}
    if tools:
        extra["tools"] = tools
        if tool_choice:
            extra["tool_choice"] = tool_choice
    try:
        completion = await client().chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=messages,
            max_completion_tokens=max_tokens,
            **extra,
            **reasoning_kwargs(),
        )
    except APIError as e:
        logger.error(f"LLM call failed: {e}")
        raise UpstreamFailed(
            "The assistant is not available right now.", code="LLM_FAILED"
        ) from e
    choice = completion.choices[0]
    usage = completion.usage
    return Reply(
        content=choice.message.content,
        tool_calls=_calls_of(choice.message),
        finish_reason=choice.finish_reason,
        tokens={"input": usage.prompt_tokens, "output": usage.completion_tokens}
        if usage
        else {},
    )


async def stream(
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 1200,
) -> AsyncIterator[StreamEvent]:
    extra: Dict[str, Any] = {"tools": tools} if tools else {}
    try:
        response = await client().chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=messages,
            max_completion_tokens=max_tokens,
            stream=True,
            **extra,
            **reasoning_kwargs(),
        )
    except APIError as e:
        logger.error(f"LLM stream failed: {e}")
        raise UpstreamFailed(
            "The assistant is not available right now.", code="LLM_FAILED"
        ) from e
    pending: Dict[int, ToolCall] = {}
    finish = None
    async for chunk in response:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta
        for part in getattr(delta, "tool_calls", None) or []:
            slot = pending.setdefault(part.index, ToolCall(id=part.id or "", name=""))
            if part.id:
                slot.id = part.id
            if part.function and part.function.name:
                slot.name = part.function.name
            if part.function and part.function.arguments:
                slot.arguments += part.function.arguments
        if delta.content:
            yield StreamEvent("text", text=delta.content)
        if choice.finish_reason:
            finish = choice.finish_reason
    if pending:
        yield StreamEvent("calls", calls=[call for _, call in sorted(pending.items())])
    yield StreamEvent("done", text=finish or "")

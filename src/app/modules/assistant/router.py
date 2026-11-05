from typing import Annotated, List

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from src.app.api.dependencies import CurrentEmployee, get_current_employee
from src.app.core.exceptions import AppError, NotFound
from src.app.core.rate_limiter import rate_limit
from src.app.database.repository_provider import RepositoryProvider, get_repos
from src.app.modules.assistant import service, stream
from src.app.modules.assistant.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    ConfirmResponse,
    ConversationOut,
    MessageOut,
)

router = APIRouter()

Current = Annotated[CurrentEmployee, Depends(get_current_employee)]
Repos = Annotated[RepositoryProvider, Depends(get_repos)]


@router.post("/chat", response_model=ChatResponse, dependencies=[rate_limit(20, 60)])
async def chat(body: ChatRequest, current: Current, repos: Repos) -> ChatResponse:
    """One turn, full answer in one JSON response."""
    final = None
    async for ev in service.turn(repos, current, body):
        if ev.kind == "done":
            final = ev.data
    return ChatResponse(**final)


@router.post("/chat/stream", dependencies=[rate_limit(20, 60)])
async def chat_stream(body: ChatRequest, current: Current, repos: Repos):
    """The same turn as server-sent events."""

    async def events():
        try:
            async for chunk in stream.sse(service.turn(repos, current, body)):
                yield chunk
        except AppError as e:
            yield stream.encode("error", {"code": e.code, "message": e.message})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/confirm/{action_id}",
    response_model=ConfirmResponse,
    dependencies=[rate_limit(20, 60)],
)
async def confirm(
    action_id: str, current: Current, repos: Repos, body: ConfirmRequest | None = None
) -> ConfirmResponse:
    decision = body.decision if body else "confirm"
    return await service.confirm(repos, current, action_id, decision)


def _conversation_out(conv, with_messages: bool) -> ConversationOut:
    return ConversationOut(
        conversationId=conv.id,
        title=conv.title,
        language=conv.language,
        createdAt=conv.created_at,
        updatedAt=conv.updated_at,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role.value,
                content=m.content,
                language=m.language,
                citations=m.citations,
                toolCalls=m.tool_calls,
                flags=m.flags,
                createdAt=m.created_at,
            )
            for m in (conv.messages if with_messages else [])
        ],
    )


@router.get(
    "/conversations",
    response_model=List[ConversationOut],
    dependencies=[rate_limit(60, 60)],
)
async def list_conversations(current: Current, repos: Repos) -> List[ConversationOut]:
    return [
        _conversation_out(c, False)
        for c in await repos.conversations.list(current.employee_id)
    ]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationOut,
    dependencies=[rate_limit(60, 60)],
)
async def get_conversation(
    conversation_id: str, current: Current, repos: Repos
) -> ConversationOut:
    conv = await repos.conversations.owned(current.employee_id, conversation_id)
    if conv is None:
        raise NotFound("Conversation not found.", code="CONVERSATION_NOT_FOUND")
    return _conversation_out(conv, True)


@router.post(
    "/conversations/{conversation_id}/title",
    response_model=ConversationOut,
    dependencies=[rate_limit(20, 60)],
)
async def regenerate_title(
    conversation_id: str, current: Current, repos: Repos
) -> ConversationOut:
    """Name the conversation again from its first question and answer."""
    return _conversation_out(
        await service.retitle(repos, current, conversation_id), False
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[rate_limit(30, 60)],
)
async def delete_conversation(
    conversation_id: str, current: Current, repos: Repos
) -> None:
    conv = await repos.conversations.owned(current.employee_id, conversation_id)
    if conv is None:
        raise NotFound("Conversation not found.", code="CONVERSATION_NOT_FOUND")
    await repos.session.delete(conv)

"""One assistant turn, end to end.

    sanitize -> scan -> detect language -> build prompt -> tool loop
    -> output checks -> persist (messages + audit) -> events

`turn` is an async generator of `TurnEvent`s so the SSE route streams
them and the JSON route collects them; both get the same `ChatResponse`
at the end. The DB session is the caller's; the generator commits
nothing itself.
"""

import secrets

from loguru import logger
from typing import Any, AsyncIterator, Dict, List, Optional

from src.app.api.dependencies import CurrentEmployee
from src.app.core.clock import utcnow
from src.app.core.config import settings
from src.app.core.exceptions import NotFound, Unavailable
from src.app.core.locale import detect
from src.app.core.templating import environment
from src.app.database.enums import AuditEventType, Language, MessageRole
from src.app.database.models import Conversation, Message
from src.app.database.repository_provider import RepositoryProvider
from src.app.core import llm
from src.app.modules.assistant import agent, confirmation
from src.app.modules.assistant.agent import TurnEvent
from src.app.modules.assistant.guardrails import injection, output, sanitize, scope
from src.app.modules.assistant.schemas import (
    Attachment,
    ChatRequest,
    ChatResponse,
    ConfirmResponse,
    PendingActionOut,
    ToolCallOut,
)
from src.app.modules.assistant.tools import ToolContext
from src.app.modules.audit import service as audit
from src.app.modules.leave import service as leave
from src.app.modules.leave.schemas import LeaveRequestCreate, LeaveRequestOut

_env = environment("assistant")
HISTORY_TURNS = 8
#: The token the system prompt asks the model to end a policy refusal with.
NO_POLICY_ANSWER = "[NO_POLICY_ANSWER]"


def render(name: str, language: Language, **ctx: Any) -> str:
    return _env.get_template(f"{name}.{language.value}.j2").render(**ctx).strip()


async def _attachments(
    repos: RepositoryProvider, items: List[Attachment]
) -> List[Dict[str, Any]]:
    out = []
    for a in items:
        if a.documentId:
            doc = await repos.untrusted_documents.get(a.documentId)
            if doc is None:
                raise NotFound(
                    "Attached document not found.", code="ATTACHMENT_NOT_FOUND"
                )
            title, raw = doc.title, f"{doc.visible_content}\n{doc.embedded_instruction}"
        else:
            title, raw = a.title or "attachment", a.content or ""
        body = sanitize.clean(raw, limit=sanitize.MAX_ATTACHMENT_CHARS)
        out.append(
            {
                "title": title,
                "body": body,
                "scan": injection.scan(body, source="attachment"),
            }
        )
    return out


async def _conversation(
    repos: RepositoryProvider,
    current: CurrentEmployee,
    conversation_id: Optional[str],
    language: Language,
) -> Conversation:
    if conversation_id:
        conv = await repos.conversations.owned(current.employee_id, conversation_id)
        if conv is None:
            raise NotFound("Conversation not found.", code="CONVERSATION_NOT_FOUND")
        return conv
    conv = Conversation(
        id=secrets.token_urlsafe(16)[:22],
        employee_id=current.employee_id,
        language=language,
        messages=[],
    )
    await repos.conversations.add(conv)
    return conv


def _history(conv: Conversation) -> List[Dict[str, str]]:
    msgs = conv.messages[-HISTORY_TURNS * 2 :]
    return [{"role": m.role.value, "content": m.content} for m in msgs]


async def name_conversation(question: str, answer: str, language: Language) -> str:
    """A short title from the first exchange, in the conversation's language.
    Falls back to the question itself if the model does not answer."""
    fallback = question.strip()[:80] or "-"
    try:
        reply = await llm.complete(
            [
                {
                    "role": "user",
                    "content": render(
                        "title", language, question=question[:500], answer=answer[:500]
                    ),
                }
            ],
            max_tokens=80,
        )
    except Exception as e:  # noqa: BLE001 - a title is never worth failing a turn for
        logger.warning(f"title generation failed: {e}")
        return fallback
    title = reply.text.strip().strip("\"'«»“”").rstrip(".。!؟?")
    return title[:80] if title else fallback


async def retitle(
    repos: RepositoryProvider, current: CurrentEmployee, conversation_id: str
) -> Conversation:
    """`POST /assistant/conversations/{id}/title` - name it again from the first exchange."""
    conv = await repos.conversations.owned(current.employee_id, conversation_id)
    if conv is None:
        raise NotFound("Conversation not found.", code="CONVERSATION_NOT_FOUND")
    question = next(
        (m.content for m in conv.messages if m.role is MessageRole.user), ""
    )
    answer = next(
        (m.content for m in conv.messages if m.role is MessageRole.assistant), ""
    )
    conv.title = await name_conversation(
        question.split("\n\n<untrusted_document")[0], answer, conv.language
    )
    await repos.session.flush()
    return conv


async def turn(
    repos: RepositoryProvider, current: CurrentEmployee, body: ChatRequest
) -> AsyncIterator[TurnEvent]:
    if not settings.llm_configured:
        raise Unavailable("The assistant is not configured.", code="LLM_NOT_CONFIGURED")

    user_text = sanitize.clean(body.message, limit=sanitize.MAX_MESSAGE_CHARS)
    language = body.language or detect(user_text)
    attachments = await _attachments(repos, body.attachments)
    user_scan = injection.scan(user_text, source="message")
    foreign = scope.foreign_ids(user_text, current.employee_id)
    injection_hits = sorted(
        {*user_scan.matches, *(m for a in attachments for m in a["scan"].matches)}
    )

    conv = await _conversation(repos, current, body.conversationId, language)
    flags: List[str] = []
    if foreign:
        flags.append("cross_employee_request")
    if injection_hits:
        flags.append("injection_suspected")
    for flag in flags:
        await audit.record(
            repos,
            current.employee_id,
            AuditEventType.guardrail_triggered,
            {"flag": flag, "foreign_ids": foreign, "patterns": injection_hits},
            conversation_id=conv.id,
        )

    system = render(
        "system",
        language,
        employee=current.employee,
        today=utcnow().date().isoformat(),
        foreign_ids=foreign,
        injection=injection_hits,
    )
    content = user_text
    for a in attachments:
        content += "\n\n" + sanitize.wrap_untrusted(a["title"], a["body"])
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        *_history(conv),
        {"role": "user", "content": content},
    ]

    await repos.conversations.add_message(
        Message(
            conversation_id=conv.id,
            role=MessageRole.user,
            content=content,
            language=language,
            flags=flags or None,
        )
    )
    yield TurnEvent(
        "meta",
        data={"conversation_id": conv.id, "language": language.value, "flags": flags},
    )

    ctx = ToolContext(
        repos=repos, current=current, language=language, conversation_id=conv.id
    )
    answer, log = "", []
    if foreign:
        # A message that names another employee is answered without the
        # model: the refusal is a fact about the server, not a judgement
        # the model is asked to make under pressure. A colleague mentioned
        # by name is still fine; only employee ids trigger this.
        answer = render("own_records", language)
        yield TurnEvent("token", text=answer)
    else:
        async for ev in agent.run_turn(ctx, messages):
            if ev.kind == "done":
                answer, log = ev.text, ev.data["tool_calls"]
            else:
                yield ev

    for entry in log:
        kind = (
            AuditEventType.tool_refused
            if entry["status"] == "refused"
            else AuditEventType.tool_called
        )
        await audit.record(
            repos,
            current.employee_id,
            kind,
            {k: v for k, v in entry.items() if k != "result"},
            conversation_id=conv.id,
        )
    if ctx.pending:
        await audit.record(
            repos,
            current.employee_id,
            AuditEventType.action_drafted,
            {"action_id": ctx.pending.action_id, "summary": ctx.pending.summary},
            conversation_id=conv.id,
        )

    refused = False
    searched = [e for e in log if e["name"] == "search_policy"]
    if NO_POLICY_ANSWER in answer:
        # The model judged the clauses it saw do not answer the question:
        # keep its wording, drop the citations (they would vouch for an
        # answer that was not given) and record the refusal.
        answer = answer.replace(NO_POLICY_ANSWER, "").strip()
        ctx.citations.clear()
        refused = True
        flags.append("unsupported_answer")
        await audit.record(
            repos,
            current.employee_id,
            AuditEventType.assistant_refused,
            {"reason": "model_no_policy_answer"},
            conversation_id=conv.id,
        )
    if searched and not ctx.citations and not refused:
        answer = render("refusal", language)
        refused = True
        flags.append("unsupported_answer")
        await audit.record(
            repos,
            current.employee_id,
            AuditEventType.assistant_refused,
            {"reason": "no_answerable_clause"},
            conversation_id=conv.id,
        )
    if any(e["status"] == "refused" for e in log) or (foreign and not log):
        if not answer.strip():
            answer = render("own_records", language)
        refused = True
    checked = output.redact_foreign_ids(answer, current.employee_id)
    answer = checked.text
    flags.extend(checked.flags)
    if not answer.strip():
        answer = render("refusal", language)

    citations = [c.model_dump(mode="json") for c in ctx.citations]
    await repos.conversations.add_message(
        Message(
            conversation_id=conv.id,
            role=MessageRole.assistant,
            content=answer,
            language=language,
            citations=citations or None,
            tool_calls=log or None,
            flags=flags or None,
        )
    )
    if conv.title is None:
        conv.title = await name_conversation(user_text, answer, language)
    conv.updated_at = utcnow()
    await audit.record(
        repos,
        current.employee_id,
        AuditEventType.chat_turn,
        {
            "language": language.value,
            "tools": [e["name"] for e in log],
            "refused": refused,
            "flags": flags,
        },
        conversation_id=conv.id,
    )

    pending = None
    if ctx.pending:
        pending = PendingActionOut(
            actionId=ctx.pending.action_id,
            kind="leave_request",
            summary=ctx.pending.summary,
            payload=ctx.pending.payload,
            expiresAt=ctx.pending.expires_at,
        )
    response = ChatResponse(
        conversationId=conv.id,
        language=language,
        answer=answer,
        citations=ctx.citations,
        toolCalls=[ToolCallOut(**e) for e in log],
        pendingAction=pending,
        refused=refused,
        flags=flags,
    )
    yield TurnEvent("done", text=answer, data=response.model_dump(mode="json"))


async def confirm(
    repos: RepositoryProvider, current: CurrentEmployee, action_id: str, decision: str
) -> ConfirmResponse:
    action = await confirmation.take(current.employee_id, action_id)
    if action is None:
        raise NotFound(
            "No pending action with this id (it may have expired).",
            code="PENDING_ACTION_NOT_FOUND",
        )
    if decision == "reject":
        await audit.record(
            repos,
            current.employee_id,
            AuditEventType.action_rejected,
            {"action_id": action_id, "summary": action.summary},
            conversation_id=action.conversation_id,
        )
        return ConfirmResponse(
            actionId=action_id, decision="reject", message="Nothing was submitted."
        )
    body = LeaveRequestCreate(**action.payload)
    row = await leave.submit(repos, current, body, confirmation_recorded=True)
    await audit.record(
        repos,
        current.employee_id,
        AuditEventType.action_confirmed,
        {"action_id": action_id, "request_id": row.id, "summary": action.summary},
        conversation_id=action.conversation_id,
    )
    if action.conversation_id:
        conv = await repos.conversations.owned(
            current.employee_id, action.conversation_id
        )
        if conv is not None:
            note = (
                f"Leave request {row.id} submitted: {action.summary}. Status: pending approval."
                if conv.language is Language.en
                else f"تم تقديم طلب الإجازة {row.id}: {action.summary}. الحالة: بانتظار الموافقة."
            )
            await repos.conversations.add_message(
                Message(
                    conversation_id=conv.id,
                    role=MessageRole.assistant,
                    content=note,
                    language=conv.language,
                    flags=["confirmed_action"],
                )
            )
    return ConfirmResponse(
        actionId=action_id,
        decision="confirm",
        result=LeaveRequestOut.from_row(row),
        message=f"Submitted as {row.id}.",
    )

"""The assistant's tools: what it may look at and what it may prepare.

One table. Each entry carries the spec the model sees, whether it is a
write, and the handler. Handlers receive a `ToolContext` holding the
caller; the caller's employee id is the only id any tool ever uses. A
handler returns a JSON-serialisable dict; refusals are returned, not
raised, so the model reads them out rather than seeing a stack trace.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import ValidationError

from src.app.api.dependencies import CurrentEmployee
from src.app.core.exceptions import AppError
from src.app.database.enums import Language, LeaveReasonCategory, LeaveType
from src.app.database.repository_provider import RepositoryProvider
from src.app.modules.assistant import confirmation
from src.app.modules.assistant.guardrails import scope
from src.app.modules.leave import service as leave
from src.app.modules.leave.schemas import LeaveRequestCreate
from src.app.modules.policies import service as policies
from src.app.modules.policies.schemas import Citation, PolicySearchRequest
from src.app.modules.procurement import service as procurement


@dataclass
class ToolContext:
    repos: RepositoryProvider
    current: CurrentEmployee
    language: Language
    conversation_id: Optional[str]
    citations: List[Citation] = field(default_factory=list)
    pending: Optional[confirmation.PendingAction] = None


Handler = Callable[[ToolContext, Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Handler
    is_write: bool = False

    @property
    def spec(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _num(value) -> float:
    return float(value)


async def get_leave_balance(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    rows = await leave.balances(ctx.repos, ctx.current)
    return {
        "employee_id": ctx.current.employee_id,
        "balances": [
            {
                "leave_type": r.leave_type.value,
                "entitled_days": _num(r.entitled_days),
                "used_days": _num(r.used_days),
                "pending_days": _num(r.pending_days),
                "available_days": _num(r.available_days),
                "as_of": r.as_of_date.isoformat(),
            }
            for r in rows
        ],
    }


async def list_leave_requests(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    rows = await leave.requests(ctx.repos, ctx.current)
    return {
        "employee_id": ctx.current.employee_id,
        "requests": [
            {
                "request_id": r.id,
                "leave_type": r.leave_type.value,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "days": r.days,
                "status": r.status.value,
            }
            for r in rows[:20]
        ],
    }


async def draft_leave_request(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and parks the request. Nothing is written here."""
    try:
        body = LeaveRequestCreate(
            leaveType=LeaveType(str(args.get("leave_type", "")).lower()),
            startDate=date.fromisoformat(str(args.get("start_date", ""))),
            endDate=date.fromisoformat(str(args.get("end_date", ""))),
            reasonCategory=LeaveReasonCategory(
                str(args.get("reason_category", "personal")).lower()
            ),
        )
    except (ValueError, ValidationError) as e:
        return {"error": "INVALID_ARGUMENTS", "message": str(e)}
    try:
        await leave.validate(ctx.repos, ctx.current, body)
    except AppError as e:
        return {"error": e.code, "message": e.message, **e.extra}
    days = (body.endDate - body.startDate).days + 1
    summary = (
        f"{body.leaveType.value} leave, {body.startDate.isoformat()} to {body.endDate.isoformat()} "
        f"({days} day{'s' if days != 1 else ''}), reason: {body.reasonCategory.value}"
    )
    action = await confirmation.park(
        ctx.current.employee_id,
        conversation_id=ctx.conversation_id,
        kind="leave_request",
        payload=body.model_dump(mode="json"),
        summary=summary,
    )
    ctx.pending = action
    return {
        "status": "confirmation_required",
        "action_id": action.action_id,
        "summary": summary,
        "days": days,
        "payload": action.payload,
        "expires_at": action.expires_at,
        "note": "Not submitted. The employee must confirm through the confirmation control.",
    }


async def get_purchase_request_status(
    ctx: ToolContext, args: Dict[str, Any]
) -> Dict[str, Any]:
    pr = str(args.get("pr_number", "")).strip()
    if not pr:
        return {"error": "INVALID_ARGUMENTS", "message": "pr_number is required"}
    try:
        row = await procurement.get_request(ctx.current, pr)
    except AppError as e:
        return {"error": e.code, "message": e.message}
    return {
        "pr_number": row.prNumber,
        "status": row.status.value,
        "current_step": row.currentStep,
        "business_purpose": row.businessPurpose,
        "amount_qar": _num(row.amountQar),
        "created_date": row.createdDate.isoformat(),
        "last_updated": row.lastUpdated.isoformat(),
    }


async def search_policy(ctx: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if len(query) < 2:
        return {"error": "INVALID_ARGUMENTS", "message": "query is required"}
    # Both languages, three each: the synthetic Arabic clauses are thin and
    # the substantive wording often sits in the English twin (or the other
    # way round), so the model should see both before it answers.
    # One clause per theme and language: the synthetic corpus repeats each
    # clause six times, and six copies of the best match would push the
    # second-best theme out of what the model sees.
    hits = []
    mode = "keyword"
    for lang in (
        ctx.language,
        Language.ar if ctx.language is Language.en else Language.en,
    ):
        result = await policies.search(
            ctx.repos, PolicySearchRequest(query=query, language=lang, limit=12)
        )
        mode = result.mode
        seen_themes = set()
        for h in result.hits:
            key = (h.citation.documentId, h.citation.theme)
            if key in seen_themes:
                continue
            seen_themes.add(key)
            hits.append(h)
            if len(seen_themes) == 3:
                break
    usable = [h.citation for h in hits if h.citation.answerable]
    for c in usable:
        if all(c.policyId != x.policyId for x in ctx.citations):
            ctx.citations.append(c)
    return {
        "query": query,
        "mode": mode,
        "clauses": [
            {
                "policy_id": c.policyId,
                "document": c.documentId.value,
                "section": c.section,
                "language": c.language.value,
                "theme": c.theme,
                "text": c.text,
            }
            for c in usable
        ],
        "note": ""
        if usable
        else "No answerable clause found. Tell the user the policy information is not available.",
    }


TOOLS: List[Tool] = [
    Tool(
        name="get_leave_balance",
        description="Leave balances (annual, sick) of the signed-in employee. No arguments.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=get_leave_balance,
    ),
    Tool(
        name="list_leave_requests",
        description="Leave requests of the signed-in employee with their status.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=list_leave_requests,
    ),
    Tool(
        name="draft_leave_request",
        description=(
            "Prepare a leave request for the signed-in employee. Validates dates and balance and "
            "returns an action_id. Does NOT submit; the employee must confirm separately."
        ),
        parameters={
            "type": "object",
            "properties": {
                "leave_type": {"type": "string", "enum": ["annual", "sick"]},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD, inclusive"},
                "reason_category": {
                    "type": "string",
                    "enum": ["family", "personal", "medical", "travel", "emergency"],
                },
            },
            "required": ["leave_type", "start_date", "end_date"],
            "additionalProperties": False,
        },
        handler=draft_leave_request,
        is_write=True,
    ),
    Tool(
        name="get_purchase_request_status",
        description="Status of one purchase request by PR number, only if it belongs to the signed-in employee.",
        parameters={
            "type": "object",
            "properties": {
                "pr_number": {"type": "string", "description": "e.g. PR-260101"}
            },
            "required": ["pr_number"],
            "additionalProperties": False,
        },
        handler=get_purchase_request_status,
    ),
    Tool(
        name="search_policy",
        description=(
            "Search the HR, procurement and information security policies. Returns clauses with "
            "ids and sections to cite. Use for every policy question before answering."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question, in the user's words",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_policy,
    ),
]
BY_NAME: Dict[str, Tool] = {t.name: t for t in TOOLS}
SPECS: List[Dict[str, Any]] = [t.spec for t in TOOLS]


def parse_args(raw: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def run(ctx: ToolContext, name: str, raw_args: str) -> Dict[str, Any]:
    """Resolve, scope-check and execute one tool call. Unknown names and
    foreign ids come back as refusals."""
    tool = BY_NAME.get(name)
    if tool is None:
        return {"error": "UNKNOWN_TOOL", "message": f"No tool named {name}."}
    args = parse_args(raw_args)
    refusal = scope.refusal_for_args(args, ctx.current.employee_id)
    if refusal:
        return refusal
    return await tool.handler(ctx, args)

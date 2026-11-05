"""Own records only, at the tool boundary.

Tool schemas never include an employee id, but a model under pressure
may still pass one, and a user may name a colleague in the question.
Both are caught here: a foreign id in a tool argument makes the tool
answer with a refusal the model must relay; a foreign id in the message
is flagged so the system prompt can tell the model to refuse up front.
"""

import re
from typing import Any, Dict, List

_EMPLOYEE_ID = re.compile(r"\bE1\d{3}\b")

#: Argument names a model might use to point at someone else.
_IDENTITY_ARGS = (
    "employee_id",
    "employeeId",
    "employee",
    "requester_id",
    "requester",
    "user_id",
    "for_employee",
)


def foreign_ids(text: str, own_id: str) -> List[str]:
    return sorted({m for m in _EMPLOYEE_ID.findall(text or "") if m != own_id})


def refusal_for_args(args: Dict[str, Any], own_id: str) -> Dict[str, Any] | None:
    """A refusal payload when the arguments try to name another employee,
    else None. Named after the caller, so the model's own wording cannot
    turn it into a success."""
    for key in _IDENTITY_ARGS:
        value = args.get(key)
        if value and str(value).strip().upper() != own_id:
            return {
                "error": "OWN_RECORDS_ONLY",
                "message": "Only the signed-in employee's own records can be accessed.",
                "requested": str(value),
            }
    return None

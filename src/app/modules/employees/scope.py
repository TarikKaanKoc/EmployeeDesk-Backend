"""The one place "own records only" is spelled out.

Every service that touches employee-owned data calls `own(current,
employee_id)` before reading or writing. Routes never take an employee id
from the client, so in practice the ids always match; the check exists so
that a future caller (a tool the model drives, an admin screen) cannot
widen the scope by accident, and so the refusal reads the same everywhere.
"""

from src.app.api.dependencies import CurrentEmployee
from src.app.core.exceptions import Forbidden


def own(current: CurrentEmployee, employee_id: str) -> str:
    if employee_id != current.employee_id:
        raise Forbidden(
            "You can only access your own records.", code="OWN_RECORDS_ONLY"
        )
    return employee_id

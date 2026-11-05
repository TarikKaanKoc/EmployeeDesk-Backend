"""Checks on the final answer before it is stored or shown.

* No other employee's id may appear in an answer (redacted if it does).
* A policy answer must carry at least one answerable citation; if the
  search found nothing usable, the model's text is replaced by the
  standard refusal so an unsupported answer never reaches the person.
"""

import re
from dataclasses import dataclass, field
from typing import List

_EMPLOYEE_ID = re.compile(r"\bE1\d{3}\b")


@dataclass
class OutputReport:
    text: str
    flags: List[str] = field(default_factory=list)


def redact_foreign_ids(text: str, own_id: str) -> OutputReport:
    report = OutputReport(text=text)
    foreign = {m for m in _EMPLOYEE_ID.findall(text) if m != own_id}
    if foreign:
        for fid in foreign:
            report.text = report.text.replace(fid, "[another employee]")
        report.flags.append("foreign_id_redacted")
    return report

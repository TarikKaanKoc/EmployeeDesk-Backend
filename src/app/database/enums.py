"""Enumerations shared by the models, the schemas and the seed loader.

Values are the stable storage form (lower snake). Labels in the synthetic
workbook ("Under Review", "Annual") are mapped to these at load time and
rendered back in the caller's language by the API.
"""

import enum


class Language(str, enum.Enum):
    en = "en"
    ar = "ar"


class EmploymentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class LeaveType(str, enum.Enum):
    annual = "annual"
    sick = "sick"


class LeaveRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class LeaveReasonCategory(str, enum.Enum):
    family = "family"
    personal = "personal"
    medical = "medical"
    travel = "travel"
    emergency = "emergency"


class PurchaseRequestStatus(str, enum.Enum):
    under_review = "under_review"
    approved = "approved"
    returned = "returned"
    rejected = "rejected"


class PolicyDomain(str, enum.Enum):
    hr = "hr"
    procurement = "procurement"
    information_security = "information_security"


class DocumentContentType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    html = "html"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class AuditEventType(str, enum.Enum):
    chat_turn = "chat.turn"
    tool_called = "tool.called"
    tool_refused = "tool.refused"
    action_drafted = "action.drafted"
    action_confirmed = "action.confirmed"
    action_rejected = "action.rejected"
    guardrail_triggered = "guardrail.triggered"
    assistant_refused = "assistant.refused"

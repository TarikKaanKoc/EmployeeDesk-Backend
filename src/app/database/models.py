"""SQLAlchemy models - the whole schema in one place.

Two Postgres schemas:

* `public`  - what the assistant owns: employees and their sign-in
  identities, leave balances and requests, the policy corpus (with
  embeddings), and the evaluation fixtures shipped with the synthetic pack.
* `erp`     - what the mock ERP owns: purchase requests. Kept in its own
  schema with no foreign key into `public`, because a real ERP is a
  separate system and the API must only ever reach it through the mock
  service's HTTP interface. The schema split makes that boundary visible
  in the database too.

Every employee-owned table carries `employee_id` with an index: "own
records only" is enforced by filtering on that column, never by trusting
an id the model or the client supplies.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.app.core.config import settings
from src.app.database.enums import (
    AuditEventType,
    DocumentContentType,
    EmploymentStatus,
    Language,
    LeaveReasonCategory,
    LeaveRequestStatus,
    LeaveType,
    MessageRole,
    PolicyDomain,
    PurchaseRequestStatus,
)

ERP_SCHEMA = "erp"


def _enum(kind, name: str) -> Enum:
    """A native Postgres enum storing the member value, not the member name."""
    return Enum(
        kind,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
    )


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Employee(TimestampMixin, Base):
    """Synthetic directory. `id` is the business key (E1001) on purpose: it is
    what every other table, the workbook and the test cases refer to."""

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    display_name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    work_location: Mapped[str] = mapped_column(String(80), nullable=False)
    email_alias: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        _enum(EmploymentStatus, "employment_status"),
        nullable=False,
        server_default=EmploymentStatus.active.value,
    )

    identities: Mapped[list["Identity"]] = relationship(back_populates="employee")
    leave_balances: Mapped[list["LeaveBalance"]] = relationship(
        back_populates="employee"
    )
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        back_populates="employee"
    )

    __table_args__ = (Index("ix_employees_department", "department"),)


class Identity(TimestampMixin, Base):
    """Sign-in subject (the `sub` claim an identity provider would issue)
    mapped to exactly one employee. The API resolves the caller from here
    and nowhere else; an inactive employee's identity is refused at login."""

    __tablename__ = "identities"

    sign_in_subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tenant: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Argon2 hash for the local password login used in tests and demos.
    #: NULL until `scripts/create_employee.py` or the seed sets one.
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))

    employee: Mapped[Employee] = relationship(back_populates="identities")


class LeaveBalance(TimestampMixin, Base):
    """One row per employee and leave type (composite key). `available_days` is a stored
    generated column, so the workbook's integrity rule (available =
    entitled - used - pending) can never drift."""

    __tablename__ = "leave_balances"

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    leave_type: Mapped[LeaveType] = mapped_column(
        _enum(LeaveType, "leave_type"), primary_key=True
    )
    entitled_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    used_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, server_default=sql_text("0")
    )
    pending_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, server_default=sql_text("0")
    )
    available_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1),
        Computed("entitled_days - used_days - pending_days", persisted=True),
        nullable=False,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="leave_balances")

    __table_args__ = (
        CheckConstraint("entitled_days >= 0", name="ck_leave_balance_entitled"),
        CheckConstraint("used_days >= 0", name="ck_leave_balance_used"),
        CheckConstraint("pending_days >= 0", name="ck_leave_balance_pending"),
    )


class LeaveRequest(TimestampMixin, Base):
    __tablename__ = "leave_requests"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    leave_type: Mapped[LeaveType] = mapped_column(
        _enum(LeaveType, "leave_type"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(
        SmallInteger, Computed("(end_date - start_date) + 1", persisted=True)
    )
    reason_category: Mapped[LeaveReasonCategory] = mapped_column(
        _enum(LeaveReasonCategory, "leave_reason_category"), nullable=False
    )
    status: Mapped[LeaveRequestStatus] = mapped_column(
        _enum(LeaveRequestStatus, "leave_request_status"),
        nullable=False,
        server_default=LeaveRequestStatus.pending.value,
    )
    #: The assistant never writes a request without an explicit confirmation;
    #: this records that the confirmation step happened for the row.
    confirmation_recorded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )

    employee: Mapped[Employee] = relationship(back_populates="leave_requests")

    __table_args__ = (
        Index("ix_leave_requests_employee_status", "employee_id", "status"),
        CheckConstraint("end_date >= start_date", name="ck_leave_request_dates"),
    )


class PolicyDocument(TimestampMixin, Base):
    """One per policy domain; the domain is the key. Clauses hang off it; a
    citation names the document, the section and the language."""

    __tablename__ = "policy_documents"

    #: The domain itself: `hr`, `procurement`, `information_security`.
    id: Mapped[PolicyDomain] = mapped_column(
        _enum(PolicyDomain, "policy_domain"), primary_key=True
    )
    title_en: Mapped[str] = mapped_column(String(160), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(160), nullable=False)

    clauses: Mapped[list["PolicyClause"]] = relationship(back_populates="document")


class PolicyClause(TimestampMixin, Base):
    """The retrieval unit. One clause = one chunk = one citation.

    `tsv` is a generated tsvector for keyword search (the `simple` config
    does no stemming, which is what we want for mixed Arabic/English text);
    `embedding` is filled by the indexer when an embedding deployment is
    configured and stays NULL otherwise, so keyword search always works.
    `answerable` is the pack's label for clauses the assistant must not
    answer from, used by the refusal tests."""

    __tablename__ = "policy_clauses"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    document_id: Mapped[PolicyDomain] = mapped_column(
        ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(16), nullable=False)
    language: Mapped[Language] = mapped_column(
        _enum(Language, "language"), nullable=False
    )
    question_theme: Mapped[str] = mapped_column(String(80), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    answerable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("true")
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSIONS)
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(String(64))
    tsv: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True)
    )

    document: Mapped[PolicyDocument] = relationship(back_populates="clauses")

    __table_args__ = (
        UniqueConstraint(
            "document_id", "section", "language", name="uq_policy_clause_section"
        ),
        Index("ix_policy_clauses_language_theme", "language", "question_theme"),
        Index("ix_policy_clauses_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_policy_clauses_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class UntrustedDocument(TimestampMixin, Base):
    """Prompt-injection fixtures: a document a user might "attach", with a
    visible body and an embedded instruction the assistant must treat as
    data. `expected_behaviour` is what the test asserts."""

    __tablename__ = "untrusted_documents"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content_type: Mapped[DocumentContentType] = mapped_column(
        _enum(DocumentContentType, "document_content_type"), nullable=False
    )
    visible_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedded_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    expected_behaviour: Mapped[str] = mapped_column(Text, nullable=False)


class AssistantTestCase(TimestampMixin, Base):
    """The pack's 100 scenarios, stored so the test runner reads them from
    the same database the API runs on and the results report can join back
    to live data."""

    __tablename__ = "assistant_test_cases"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    signed_in_employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[Language] = mapped_column(
        _enum(Language, "language"), nullable=False
    )
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    expected_tool_action: Mapped[str] = mapped_column(String(160), nullable=False)
    expected_result: Mapped[str] = mapped_column(String(160), nullable=False)
    expected_citation: Mapped[str] = mapped_column(String(80), nullable=False)
    write_confirmation_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )


class Conversation(TimestampMixin, Base):
    """One chat thread, owned by one employee."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(160))
    language: Mapped[Language] = mapped_column(
        _enum(Language, "language"), nullable=False, server_default=Language.en.value
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        order_by="Message.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_conversations_employee", "employee_id", "updated_at"),)


class Message(Base):
    """A user or assistant turn. `citations`, `tool_calls` and `flags` are
    what the assistant did and why; they are what the audit trail and the
    evaluation report read back."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        _enum(MessageRole, "message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Language] = mapped_column(
        _enum(Language, "language"), nullable=False
    )
    citations: Mapped[Optional[list]] = mapped_column(JSONB)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSONB)
    flags: Mapped[Optional[list]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_conversation", "conversation_id", "id"),)


class AuditEvent(Base):
    """Append-only. Every tool call, refusal, draft and confirmation lands
    here with the employee it concerns."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        _enum(AuditEventType, "audit_event_type"), nullable=False
    )
    conversation_id: Mapped[Optional[str]] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_audit_employee_time", "employee_id", "created_at"),)


class PurchaseRequest(Base):
    """What the mock ERP serves. `requester_employee_id` is deliberately not
    a foreign key: the ERP is modelled as another system that merely
    shares identifiers with HR. Business dates (`created_date`,
    `last_updated`) are the ERP's own; no load-time timestamps here."""

    __tablename__ = "purchase_requests"
    __table_args__ = (
        Index("ix_erp_pr_requester", "requester_employee_id"),
        CheckConstraint("amount_qar >= 0", name="ck_erp_pr_amount"),
        {"schema": ERP_SCHEMA},
    )

    pr_number: Mapped[str] = mapped_column(String(16), primary_key=True)
    requester_employee_id: Mapped[str] = mapped_column(String(16), nullable=False)
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    business_purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_qar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[PurchaseRequestStatus] = mapped_column(
        _enum(PurchaseRequestStatus, "purchase_request_status"), nullable=False
    )
    current_step: Mapped[str] = mapped_column(String(80), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_updated: Mapped[date] = mapped_column(Date, nullable=False)
    mock_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

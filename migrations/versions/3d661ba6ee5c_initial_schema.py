"""initial schema

Revision ID: 3d661ba6ee5c
Revises:
Create Date: 2026-11-04 23:48:54.815749
"""

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3d661ba6ee5c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions, schemas and enum types first: several tables share the
    # same enum, so they are created once here rather than per table.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS erp")
    op.execute("CREATE TYPE employment_status AS ENUM ('active', 'inactive')")
    op.execute("CREATE TYPE language AS ENUM ('en', 'ar')")
    op.execute("CREATE TYPE leave_type AS ENUM ('annual', 'sick')")
    op.execute(
        "CREATE TYPE leave_request_status AS ENUM ('pending', 'approved', 'rejected', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE leave_reason_category AS ENUM ('family', 'personal', 'medical', 'travel', 'emergency')"
    )
    op.execute(
        "CREATE TYPE purchase_request_status AS ENUM ('under_review', 'approved', 'returned', 'rejected')"
    )
    op.execute(
        "CREATE TYPE policy_domain AS ENUM ('hr', 'procurement', 'information_security')"
    )
    op.execute("CREATE TYPE document_content_type AS ENUM ('pdf', 'docx', 'html')")

    op.create_table(
        "employees",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("display_name_en", sa.String(length=120), nullable=False),
        sa.Column("display_name_ar", sa.String(length=120), nullable=False),
        sa.Column("department", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("work_location", sa.String(length=80), nullable=False),
        sa.Column("email_alias", sa.String(length=120), nullable=False),
        sa.Column(
            "employment_status",
            postgresql.ENUM(
                "active", "inactive", name="employment_status", create_type=False
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_alias"),
    )
    op.create_index(
        "ix_employees_department", "employees", ["department"], unique=False
    )
    op.create_table(
        "purchase_requests",
        sa.Column("pr_number", sa.String(length=16), nullable=False),
        sa.Column("requester_employee_id", sa.String(length=16), nullable=False),
        sa.Column("department", sa.String(length=80), nullable=False),
        sa.Column("business_purpose", sa.String(length=200), nullable=False),
        sa.Column("amount_qar", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "under_review",
                "approved",
                "returned",
                "rejected",
                name="purchase_request_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("current_step", sa.String(length=80), nullable=False),
        sa.Column("created_date", sa.Date(), nullable=False),
        sa.Column("last_updated", sa.Date(), nullable=False),
        sa.Column("mock_reference", sa.String(length=32), nullable=False),
        sa.CheckConstraint("amount_qar >= 0", name="ck_erp_pr_amount"),
        sa.PrimaryKeyConstraint("pr_number"),
        sa.UniqueConstraint("mock_reference"),
        schema="erp",
    )
    op.create_index(
        "ix_erp_pr_requester",
        "purchase_requests",
        ["requester_employee_id"],
        unique=False,
        schema="erp",
    )
    op.create_table(
        "policy_documents",
        sa.Column(
            "id",
            postgresql.ENUM(
                "hr",
                "procurement",
                "information_security",
                name="policy_domain",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title_en", sa.String(length=160), nullable=False),
        sa.Column("title_ar", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "untrusted_documents",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column(
            "content_type",
            postgresql.ENUM(
                "pdf", "docx", "html", name="document_content_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("visible_content", sa.Text(), nullable=False),
        sa.Column("embedded_instruction", sa.Text(), nullable=False),
        sa.Column("expected_behaviour", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assistant_test_cases",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("signed_in_employee_id", sa.String(length=16), nullable=False),
        sa.Column(
            "language",
            postgresql.ENUM("en", "ar", name="language", create_type=False),
            nullable=False,
        ),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("expected_tool_action", sa.String(length=160), nullable=False),
        sa.Column("expected_result", sa.String(length=160), nullable=False),
        sa.Column("expected_citation", sa.String(length=80), nullable=False),
        sa.Column(
            "write_confirmation_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["signed_in_employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "identities",
        sa.Column("sign_in_subject", sa.String(length=128), nullable=False),
        sa.Column("employee_id", sa.String(length=16), nullable=False),
        sa.Column("tenant", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sign_in_subject"),
        sa.UniqueConstraint("employee_id"),
    )
    op.create_table(
        "leave_balances",
        sa.Column("employee_id", sa.String(length=16), nullable=False),
        sa.Column(
            "leave_type",
            postgresql.ENUM("annual", "sick", name="leave_type", create_type=False),
            nullable=False,
        ),
        sa.Column("entitled_days", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column(
            "used_days",
            sa.Numeric(precision=5, scale=1),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "pending_days",
            sa.Numeric(precision=5, scale=1),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "available_days",
            sa.Numeric(precision=5, scale=1),
            sa.Computed("entitled_days - used_days - pending_days", persisted=True),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("entitled_days >= 0", name="ck_leave_balance_entitled"),
        sa.CheckConstraint("pending_days >= 0", name="ck_leave_balance_pending"),
        sa.CheckConstraint("used_days >= 0", name="ck_leave_balance_used"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("employee_id", "leave_type"),
    )
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("employee_id", sa.String(length=16), nullable=False),
        sa.Column(
            "leave_type",
            postgresql.ENUM("annual", "sick", name="leave_type", create_type=False),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "days",
            sa.SmallInteger(),
            sa.Computed("(end_date - start_date) + 1", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "reason_category",
            postgresql.ENUM(
                "family",
                "personal",
                "medical",
                "travel",
                "emergency",
                name="leave_reason_category",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "cancelled",
                name="leave_request_status",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "confirmation_recorded",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_leave_request_dates"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_leave_requests_employee_status",
        "leave_requests",
        ["employee_id", "status"],
        unique=False,
    )
    op.create_table(
        "policy_clauses",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column(
            "document_id",
            postgresql.ENUM(
                "hr",
                "procurement",
                "information_security",
                name="policy_domain",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("section", sa.String(length=16), nullable=False),
        sa.Column(
            "language",
            postgresql.ENUM("en", "ar", name="language", create_type=False),
            nullable=False,
        ),
        sa.Column("question_theme", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "answerable", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True
        ),
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["policy_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "section", "language", name="uq_policy_clause_section"
        ),
    )
    op.create_index(
        "ix_policy_clauses_embedding",
        "policy_clauses",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_policy_clauses_language_theme",
        "policy_clauses",
        ["language", "question_theme"],
        unique=False,
    )
    op.create_index(
        "ix_policy_clauses_tsv",
        "policy_clauses",
        ["tsv"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_policy_clauses_tsv", table_name="policy_clauses", postgresql_using="gin"
    )
    op.drop_index("ix_policy_clauses_language_theme", table_name="policy_clauses")
    op.drop_index(
        "ix_policy_clauses_embedding",
        table_name="policy_clauses",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("policy_clauses")
    op.drop_index("ix_leave_requests_employee_status", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_table("leave_balances")
    op.drop_table("identities")
    op.drop_table("assistant_test_cases")
    op.drop_table("untrusted_documents")
    op.drop_table("policy_documents")
    op.drop_index("ix_erp_pr_requester", table_name="purchase_requests", schema="erp")
    op.drop_table("purchase_requests", schema="erp")
    op.drop_index("ix_employees_department", table_name="employees")
    op.drop_table("employees")
    for name in (
        "employment_status",
        "language",
        "leave_type",
        "leave_request_status",
        "leave_reason_category",
        "purchase_request_status",
        "policy_domain",
        "document_content_type",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")
    op.execute("DROP SCHEMA IF EXISTS erp")

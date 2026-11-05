"""assistant tables: conversations, messages, audit_events

Revision ID: b47e0d1c52a9
Revises: 8c1f2a7d9b31
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b47e0d1c52a9"
down_revision: Union[str, None] = "8c1f2a7d9b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant')")
    op.execute(
        "CREATE TYPE audit_event_type AS ENUM ('chat.turn', 'tool.called', 'tool.refused', "
        "'action.drafted', 'action.confirmed', 'action.rejected', 'guardrail.triggered', "
        "'assistant.refused')"
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("employee_id", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column(
            "language",
            postgresql.ENUM("en", "ar", name="language", create_type=False),
            server_default="en",
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_employee", "conversations", ["employee_id", "updated_at"]
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "user", "assistant", name="message_role", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "language",
            postgresql.ENUM("en", "ar", name="language", create_type=False),
            nullable=False,
        ),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation", "messages", ["conversation_id", "id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.String(length=16), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "chat.turn",
                "tool.called",
                "tool.refused",
                "action.drafted",
                "action.confirmed",
                "action.rejected",
                "guardrail.triggered",
                "assistant.refused",
                name="audit_event_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.String(length=32), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_employee_time", "audit_events", ["employee_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP TYPE IF EXISTS audit_event_type")
    op.execute("DROP TYPE IF EXISTS message_role")

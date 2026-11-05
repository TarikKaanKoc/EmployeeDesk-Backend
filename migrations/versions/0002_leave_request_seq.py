"""leave request id sequence

Revision ID: 8c1f2a7d9b31
Revises: 3d661ba6ee5c
Create Date: 2026-11-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "8c1f2a7d9b31"
down_revision: Union[str, None] = "3d661ba6ee5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New requests continue the pack's numbering (LR-9001 .. LR-9120).
    op.execute("CREATE SEQUENCE IF NOT EXISTS leave_request_seq START WITH 9121")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS leave_request_seq")

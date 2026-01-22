"""Create reports table.

Revision ID: 20260122_add_reports_table
Revises: 20260122_merge_group_chat_member_roles_and_user_dob
Create Date: 2026-01-22

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260122_add_reports_table"
down_revision: str = "20260122_merge_group_chat_member_roles_and_user_dob"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "reports" in inspector.get_table_names():
        return

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_taken", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    op.create_index("ix_reports_target_type", "reports", ["target_type"])
    op.create_index("ix_reports_target_id", "reports", ["target_id"])
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_target_user_id", "reports", ["target_user_id"])

    op.create_unique_constraint(
        "uq_reports_reporter_target",
        "reports",
        ["reporter_id", "target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_reports_reporter_target", "reports", type_="unique")
    op.drop_index("ix_reports_target_user_id", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_target_id", table_name="reports")
    op.drop_index("ix_reports_target_type", table_name="reports")
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_table("reports")

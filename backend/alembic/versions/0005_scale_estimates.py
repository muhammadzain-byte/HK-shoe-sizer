"""scale estimates

Revision ID: 0005_scale_estimates
Revises: 0004_capture_sessions
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_scale_estimates"
down_revision: str | None = "0004_capture_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scale_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("foot_scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("foot_measurement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capture_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scale_status", sa.String(length=32), nullable=False),
        sa.Column("scale_mode", sa.String(length=64), nullable=False),
        sa.Column("pixels_per_mm", sa.Float(), nullable=True),
        sa.Column("mm_per_pixel", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("instructions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("foot_length_mm", sa.Float(), nullable=True),
        sa.Column("foot_width_mm", sa.Float(), nullable=True),
        sa.Column("can_recommend_size", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["capture_session_id"], ["capture_sessions.id"]),
        sa.ForeignKeyConstraint(["foot_measurement_id"], ["foot_measurements.id"]),
        sa.ForeignKeyConstraint(["foot_scan_id"], ["foot_scans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scale_estimates_user_id", "scale_estimates", ["user_id"], unique=False)
    op.create_index("ix_scale_estimates_foot_scan_id", "scale_estimates", ["foot_scan_id"], unique=False)
    op.create_index(
        "ix_scale_estimates_capture_session_id",
        "scale_estimates",
        ["capture_session_id"],
        unique=False,
    )
    op.create_index("ix_scale_estimates_scale_status", "scale_estimates", ["scale_status"], unique=False)
    op.create_index("ix_scale_estimates_scale_mode", "scale_estimates", ["scale_mode"], unique=False)
    op.create_index("ix_scale_estimates_created_at", "scale_estimates", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scale_estimates_created_at", table_name="scale_estimates")
    op.drop_index("ix_scale_estimates_scale_mode", table_name="scale_estimates")
    op.drop_index("ix_scale_estimates_scale_status", table_name="scale_estimates")
    op.drop_index("ix_scale_estimates_capture_session_id", table_name="scale_estimates")
    op.drop_index("ix_scale_estimates_foot_scan_id", table_name="scale_estimates")
    op.drop_index("ix_scale_estimates_user_id", table_name="scale_estimates")
    op.drop_table("scale_estimates")

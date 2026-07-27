"""foot measurements

Revision ID: 0003_foot_measurements
Revises: 0002_scan_validation_fields
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_foot_measurements"
down_revision: str | None = "0002_scan_validation_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foot_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("foot_length_pixels", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("foot_width_pixels", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("heel_x", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("heel_y", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("toe_x", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("toe_y", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("width_left_x", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("width_left_y", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("width_right_x", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("width_right_y", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("measurement_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["foot_scans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_foot_measurements_scan_id"), "foot_measurements", ["scan_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_foot_measurements_scan_id"), table_name="foot_measurements")
    op.drop_table("foot_measurements")

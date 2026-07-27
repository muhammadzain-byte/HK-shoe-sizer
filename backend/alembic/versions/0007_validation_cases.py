"""validation cases

Revision ID: 0007_validation_cases
Revises: 0006_shoe_recommendations
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_validation_cases"
down_revision: str | None = "0006_shoe_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "validation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("case_label", sa.String(length=255), nullable=True),
        sa.Column("image_upload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capture_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_label", sa.String(length=255), nullable=True),
        sa.Column("device_os", sa.String(length=128), nullable=True),
        sa.Column("browser", sa.String(length=128), nullable=True),
        sa.Column("camera_type", sa.String(length=128), nullable=True),
        sa.Column("foot_side", sa.String(length=16), nullable=True),
        sa.Column("capture_scenario", sa.String(length=128), nullable=True),
        sa.Column("ground_truth_length_mm", sa.Float(), nullable=True),
        sa.Column("ground_truth_width_mm", sa.Float(), nullable=True),
        sa.Column("ground_truth_source", sa.String(length=128), nullable=True),
        sa.Column("reference_mode", sa.String(length=64), nullable=False, server_default="none"),
        sa.Column("reference_width_mm", sa.Float(), nullable=True),
        sa.Column("reference_height_mm", sa.Float(), nullable=True),
        sa.Column("reference_bbox_x", sa.Float(), nullable=True),
        sa.Column("reference_bbox_y", sa.Float(), nullable=True),
        sa.Column("reference_bbox_width", sa.Float(), nullable=True),
        sa.Column("reference_bbox_height", sa.Float(), nullable=True),
        sa.Column("reference_polygon_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["capture_session_id"], ["capture_sessions.id"]),
        sa.ForeignKeyConstraint(["image_upload_id"], ["uploaded_images.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["foot_scans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_cases_user_id", "validation_cases", ["user_id"], unique=False)
    op.create_index("ix_validation_cases_case_id", "validation_cases", ["case_id"], unique=False)
    op.create_index("ix_validation_cases_scan_id", "validation_cases", ["scan_id"], unique=False)
    op.create_index("ix_validation_cases_status", "validation_cases", ["status"], unique=False)
    op.create_index("ix_validation_cases_device_os", "validation_cases", ["device_os"], unique=False)
    op.create_index(
        "ix_validation_cases_capture_scenario",
        "validation_cases",
        ["capture_scenario"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_validation_cases_capture_scenario", table_name="validation_cases")
    op.drop_index("ix_validation_cases_device_os", table_name="validation_cases")
    op.drop_index("ix_validation_cases_status", table_name="validation_cases")
    op.drop_index("ix_validation_cases_scan_id", table_name="validation_cases")
    op.drop_index("ix_validation_cases_case_id", table_name="validation_cases")
    op.drop_index("ix_validation_cases_user_id", table_name="validation_cases")
    op.drop_table("validation_cases")

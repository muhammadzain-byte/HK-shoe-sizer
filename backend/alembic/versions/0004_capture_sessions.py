"""capture sessions

Revision ID: 0004_capture_sessions
Revises: 0003_foot_measurements
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_capture_sessions"
down_revision: str | None = "0003_foot_measurements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("foot_scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_image_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capture_status", sa.String(length=32), nullable=False),
        sa.Column("capture_quality_score", sa.Float(), nullable=False),
        sa.Column("primary_instruction", sa.Text(), nullable=True),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("instructions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("lighting_score", sa.Float(), nullable=True),
        sa.Column("overexposure_score", sa.Float(), nullable=True),
        sa.Column("foot_detected", sa.Boolean(), nullable=True),
        sa.Column("one_foot_only", sa.Boolean(), nullable=True),
        sa.Column("toes_visible", sa.Boolean(), nullable=True),
        sa.Column("heel_visible", sa.Boolean(), nullable=True),
        sa.Column("full_foot_visible", sa.Boolean(), nullable=True),
        sa.Column("lower_leg_ratio", sa.Float(), nullable=True),
        sa.Column("toe_margin_ratio", sa.Float(), nullable=True),
        sa.Column("heel_margin_ratio", sa.Float(), nullable=True),
        sa.Column("side_margin_ratio", sa.Float(), nullable=True),
        sa.Column("top_down_score", sa.Float(), nullable=True),
        sa.Column("rotation_angle_degrees", sa.Float(), nullable=True),
        sa.Column("perspective_risk", sa.Float(), nullable=True),
        sa.Column("foot_flatness_risk", sa.Float(), nullable=True),
        sa.Column("foot_frame_coverage", sa.Float(), nullable=True),
        sa.Column("too_close", sa.Boolean(), nullable=True),
        sa.Column("too_far", sa.Boolean(), nullable=True),
        sa.Column("distance_confidence", sa.Float(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("browser", sa.String(length=128), nullable=True),
        sa.Column("os", sa.String(length=128), nullable=True),
        sa.Column("device_type", sa.String(length=128), nullable=True),
        sa.Column("device_family", sa.String(length=128), nullable=True),
        sa.Column("viewport_width", sa.Integer(), nullable=True),
        sa.Column("viewport_height", sa.Integer(), nullable=True),
        sa.Column("video_width", sa.Integer(), nullable=True),
        sa.Column("video_height", sa.Integer(), nullable=True),
        sa.Column("device_pixel_ratio", sa.Float(), nullable=True),
        sa.Column("facing_mode", sa.String(length=64), nullable=True),
        sa.Column("orientation_alpha", sa.Float(), nullable=True),
        sa.Column("orientation_beta", sa.Float(), nullable=True),
        sa.Column("orientation_gamma", sa.Float(), nullable=True),
        sa.Column("motion", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_device_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_capture_quality_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["foot_scan_id"], ["foot_scans.id"]),
        sa.ForeignKeyConstraint(["uploaded_image_id"], ["uploaded_images.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capture_sessions_user_id", "capture_sessions", ["user_id"], unique=False)
    op.create_index("ix_capture_sessions_foot_scan_id", "capture_sessions", ["foot_scan_id"], unique=False)
    op.create_index(
        "ix_capture_sessions_uploaded_image_id", "capture_sessions", ["uploaded_image_id"], unique=False
    )
    op.create_index(
        "ix_capture_sessions_capture_status", "capture_sessions", ["capture_status"], unique=False
    )
    op.create_index("ix_capture_sessions_created_at", "capture_sessions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_capture_sessions_created_at", table_name="capture_sessions")
    op.drop_index("ix_capture_sessions_capture_status", table_name="capture_sessions")
    op.drop_index("ix_capture_sessions_uploaded_image_id", table_name="capture_sessions")
    op.drop_index("ix_capture_sessions_foot_scan_id", table_name="capture_sessions")
    op.drop_index("ix_capture_sessions_user_id", table_name="capture_sessions")
    op.drop_table("capture_sessions")

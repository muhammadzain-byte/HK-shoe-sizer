"""validation benchmark results

Revision ID: 0008_validation_benchmarks
Revises: 0007_validation_cases
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_validation_benchmarks"
down_revision: str | None = "0007_validation_cases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "validation_benchmark_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validation_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("measured_length_mm", sa.Float(), nullable=True),
        sa.Column("measured_width_mm", sa.Float(), nullable=True),
        sa.Column("ground_truth_length_mm", sa.Float(), nullable=True),
        sa.Column("ground_truth_width_mm", sa.Float(), nullable=True),
        sa.Column("length_error_mm", sa.Float(), nullable=True),
        sa.Column("width_error_mm", sa.Float(), nullable=True),
        sa.Column("length_abs_error_mm", sa.Float(), nullable=True),
        sa.Column("width_abs_error_mm", sa.Float(), nullable=True),
        sa.Column("length_error_percent", sa.Float(), nullable=True),
        sa.Column("width_error_percent", sa.Float(), nullable=True),
        sa.Column("capture_status", sa.String(length=32), nullable=True),
        sa.Column("measurement_status", sa.String(length=32), nullable=True),
        sa.Column("scale_status", sa.String(length=32), nullable=True),
        sa.Column("size_status", sa.String(length=64), nullable=True),
        sa.Column("recommended_size_system", sa.String(length=32), nullable=True),
        sa.Column("recommended_size", sa.String(length=32), nullable=True),
        sa.Column("failure_stage", sa.String(length=64), nullable=True),
        sa.Column("failure_reasons_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pipeline_output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["foot_scans.id"]),
        sa.ForeignKeyConstraint(["validation_case_id"], ["validation_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_validation_benchmark_results_validation_case_id",
        "validation_benchmark_results",
        ["validation_case_id"],
        unique=False,
    )
    op.create_index(
        "ix_validation_benchmark_results_scan_id",
        "validation_benchmark_results",
        ["scan_id"],
        unique=False,
    )
    op.create_index(
        "ix_validation_benchmark_results_failure_stage",
        "validation_benchmark_results",
        ["failure_stage"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validation_benchmark_results_failure_stage",
        table_name="validation_benchmark_results",
    )
    op.drop_index("ix_validation_benchmark_results_scan_id", table_name="validation_benchmark_results")
    op.drop_index(
        "ix_validation_benchmark_results_validation_case_id",
        table_name="validation_benchmark_results",
    )
    op.drop_table("validation_benchmark_results")

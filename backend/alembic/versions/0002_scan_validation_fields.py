"""scan validation fields

Revision ID: 0002_scan_validation_fields
Revises: 0001_initial_schema
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_scan_validation_fields"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("foot_scans")}
    if "validation_status" not in existing_columns:
        op.add_column("foot_scans", sa.Column("validation_status", sa.String(length=32), nullable=True))
    if "validation_issues" not in existing_columns:
        op.add_column(
            "foot_scans",
            sa.Column("validation_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    existing_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("foot_scans")}
    if "validation_issues" in existing_columns:
        op.drop_column("foot_scans", "validation_issues")
    if "validation_status" in existing_columns:
        op.drop_column("foot_scans", "validation_status")

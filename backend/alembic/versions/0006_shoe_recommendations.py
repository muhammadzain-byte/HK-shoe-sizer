"""shoe recommendation safety fields

Revision ID: 0006_shoe_recommendations
Revises: 0005_scale_estimates
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_shoe_recommendations"
down_revision: str | None = "0005_scale_estimates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shoe_recommendations", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "shoe_recommendations", sa.Column("scale_estimate_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("shoe_recommendations", sa.Column("gender", sa.String(length=32), nullable=True))
    op.add_column("shoe_recommendations", sa.Column("shoe_type", sa.String(length=64), nullable=True))
    op.add_column("shoe_recommendations", sa.Column("fit_preference", sa.String(length=64), nullable=True))
    op.add_column("shoe_recommendations", sa.Column("recommendation_status", sa.String(length=64), nullable=True))
    op.add_column("shoe_recommendations", sa.Column("recommended_size", sa.String(length=32), nullable=True))
    op.add_column("shoe_recommendations", sa.Column("size_system", sa.String(length=32), nullable=True))
    op.add_column("shoe_recommendations", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column(
        "shoe_recommendations",
        sa.Column("reasoning", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "shoe_recommendations",
        sa.Column("alternate_sizes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "shoe_recommendations",
        sa.Column("fit_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("shoe_recommendations", sa.Column("blocked_reason", sa.Text(), nullable=True))
    op.alter_column(
        "shoe_recommendations",
        "confidence_score",
        existing_type=sa.Numeric(precision=5, scale=4),
        type_=sa.Float(),
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_shoe_recommendations_user_id_users",
        "shoe_recommendations",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_shoe_recommendations_scale_estimate_id_scale_estimates",
        "shoe_recommendations",
        "scale_estimates",
        ["scale_estimate_id"],
        ["id"],
    )
    op.create_index("ix_shoe_recommendations_user_id", "shoe_recommendations", ["user_id"], unique=False)
    op.create_index(
        "ix_shoe_recommendations_scale_estimate_id",
        "shoe_recommendations",
        ["scale_estimate_id"],
        unique=False,
    )
    op.create_index(
        "ix_shoe_recommendations_recommendation_status",
        "shoe_recommendations",
        ["recommendation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shoe_recommendations_recommendation_status", table_name="shoe_recommendations")
    op.drop_index("ix_shoe_recommendations_scale_estimate_id", table_name="shoe_recommendations")
    op.drop_index("ix_shoe_recommendations_user_id", table_name="shoe_recommendations")
    op.drop_constraint(
        "fk_shoe_recommendations_scale_estimate_id_scale_estimates",
        "shoe_recommendations",
        type_="foreignkey",
    )
    op.drop_constraint("fk_shoe_recommendations_user_id_users", "shoe_recommendations", type_="foreignkey")
    op.alter_column(
        "shoe_recommendations",
        "confidence_score",
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=5, scale=4),
        existing_nullable=True,
    )
    op.drop_column("shoe_recommendations", "blocked_reason")
    op.drop_column("shoe_recommendations", "fit_notes")
    op.drop_column("shoe_recommendations", "alternate_sizes")
    op.drop_column("shoe_recommendations", "reasoning")
    op.drop_column("shoe_recommendations", "confidence")
    op.drop_column("shoe_recommendations", "size_system")
    op.drop_column("shoe_recommendations", "recommended_size")
    op.drop_column("shoe_recommendations", "recommendation_status")
    op.drop_column("shoe_recommendations", "fit_preference")
    op.drop_column("shoe_recommendations", "shoe_type")
    op.drop_column("shoe_recommendations", "gender")
    op.drop_column("shoe_recommendations", "scale_estimate_id")
    op.drop_column("shoe_recommendations", "user_id")

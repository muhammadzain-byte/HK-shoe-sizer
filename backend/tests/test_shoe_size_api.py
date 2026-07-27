import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("aws_s3_bucket", "test-bucket")


def test_shoe_size_route_is_registered() -> None:
    from app.api.v1.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/ai/scans/{scan_id}/shoe-size" in paths


def test_shoe_recommendation_migration_is_registered() -> None:
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0006_shoe_recommendations.py"

    assert migration.exists()
    assert "shoe_recommendations" in migration.read_text(encoding="utf-8")

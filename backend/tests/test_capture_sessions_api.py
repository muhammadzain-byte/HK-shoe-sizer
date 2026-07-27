import os
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("aws_s3_bucket", "test-bucket")


def test_capture_session_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/capture-sessions" in paths
    assert "/capture-sessions/{capture_session_id}" in paths
    assert "/capture-sessions/{capture_session_id}/attach" in paths
    assert "/scans/{scan_id}/capture-sessions" in paths


def test_ai_capture_quality_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/ai/capture-quality" in paths
    assert "/ai/scans/{scan_id}/capture-quality" in paths


def test_capture_quality_response_preserves_old_shape_without_session() -> None:
    from app.api.v1.ai import _capture_quality_response

    quality = {"capture_status": "ready", "score": 0.9}

    assert _capture_quality_response(quality) == quality


def test_capture_quality_response_wraps_persisted_session() -> None:
    from app.api.v1.ai import _capture_quality_response

    quality = {"capture_status": "ready", "score": 0.9}
    session_id = uuid4()

    response = _capture_quality_response(quality, session_id)

    assert response["capture_quality"] == quality
    assert response["capture_session_id"] == str(session_id)


def test_capture_sessions_migration_is_registered() -> None:
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0004_capture_sessions.py"

    assert migration.exists()
    assert "capture_sessions" in migration.read_text(encoding="utf-8")

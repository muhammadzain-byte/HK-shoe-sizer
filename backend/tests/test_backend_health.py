import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")


def test_health_route_returns_readiness_contract() -> None:
    router = Path(__file__).parents[1] / "app" / "api" / "v1" / "router.py"
    source = router.read_text(encoding="utf-8")

    assert '@api_router.get("/health"' in source
    assert '"status": "ok" if all_ready else "error"' in source
    assert '"validation_tables": validation_tables' in source
    assert '"auth_ready": auth_ready' in source
    assert '"local_upload_ready": local_upload_ready' in source
    assert '"issues": issues' in source

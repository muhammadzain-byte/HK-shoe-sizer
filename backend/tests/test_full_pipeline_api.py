import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("aws_s3_bucket", "test-bucket")


def test_full_pipeline_route_is_registered() -> None:
    from app.api.v1.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/ai/scans/{scan_id}/run-full-pipeline" in paths


def test_reference_object_detection_route_is_registered() -> None:
    from app.api.v1.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/ai/scans/{scan_id}/detect-reference-object" in paths

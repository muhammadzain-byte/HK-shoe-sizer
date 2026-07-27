import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


def test_validation_case_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {route.path for route in api_router.routes}

    assert "/validation-cases" in paths
    assert "/validation-cases/summary" in paths
    assert "/validation-cases/{validation_case_id}/run-benchmark" in paths
    assert "/validation-cases/{validation_case_id}/mark-benchmark-ready" in paths

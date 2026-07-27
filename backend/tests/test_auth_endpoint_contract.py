import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")


def test_auth_endpoint_paths_match_frontend_contract() -> None:
    from app.api.v1.router import api_router

    route_methods = {
        route.path: getattr(route, "methods", set())
        for route in api_router.routes
        if route.path.startswith("/auth") or route.path == "/health"
    }

    assert "POST" in route_methods["/auth/register"]
    assert "POST" in route_methods["/auth/login"]
    assert "GET" in route_methods["/auth/me"]
    assert "GET" in route_methods["/health"]


def test_research_models_remain_disabled_by_default() -> None:
    from app.core.config import Settings

    assert Settings().enable_research_models is False

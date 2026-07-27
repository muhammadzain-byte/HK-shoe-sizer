from pathlib import Path


def test_api_v1_root_returns_helpful_service_json() -> None:
    router = Path(__file__).parents[1] / "app" / "api" / "v1" / "router.py"
    source = router.read_text(encoding="utf-8")

    assert '@api_router.get("", tags=["health"])' in source
    assert '"service": "MirrorStep API"' in source
    assert '"health_url": "/api/v1/health"' in source
    assert '"docs_url": "/docs"' in source

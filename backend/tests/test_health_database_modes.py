from pathlib import Path


def test_health_endpoint_reports_database_modes_and_fallback_warning() -> None:
    router = Path(__file__).parents[1] / "app" / "api" / "v1" / "router.py"
    source = router.read_text(encoding="utf-8")

    assert '"database_mode": database_mode' in source
    assert "sqlite_testing_fallback" in source
    assert "PostgreSQL" not in source or "production accuracy evidence" in source
    assert '"research_models_enabled": settings.enable_research_models' in source


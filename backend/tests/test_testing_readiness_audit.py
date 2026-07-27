def test_audit_script_does_not_crash_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")

    from scripts.audit_testing_readiness import audit_testing_readiness

    report = audit_testing_readiness()

    assert report["database_url_present"] is False
    assert report["ready_for_testing"] is False
    assert any("DATABASE_URL" in issue for issue in report["issues"])


def test_research_models_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_RESEARCH_MODELS", raising=False)

    from app.core.config import Settings

    assert Settings().enable_research_models is False

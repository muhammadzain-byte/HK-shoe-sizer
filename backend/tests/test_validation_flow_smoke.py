def test_validation_flow_smoke_reports_db_missing_safely(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.smoke_test_validation_flow import smoke_test_validation_flow

    report = smoke_test_validation_flow()

    assert report["db_ready"] is False
    assert report["benchmark_run"] is False
    assert "DATABASE_URL" in report["benchmark_blocker"]

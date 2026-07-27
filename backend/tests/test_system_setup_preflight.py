def test_system_setup_preflight_reports_without_crashing(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.system_setup_preflight import system_setup_preflight

    report = system_setup_preflight()

    assert "python_ok" in report
    assert report["database_url_present"] is False
    assert isinstance(report["next_steps"], list)

def test_verify_validation_tables_reports_missing_db_safely(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.verify_validation_tables import verify_validation_tables

    report = verify_validation_tables()

    assert report["database_connected"] is False
    assert report["all_required_tables_exist"] is False
    assert "DATABASE_URL is not set." in report["issues"]

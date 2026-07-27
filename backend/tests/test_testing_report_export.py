def test_testing_report_exports_blocked_accuracy_with_zero_cases(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.export_testing_report import export_testing_report

    report = export_testing_report()

    assert report["db_ready"] is False
    assert report["accuracy_claim_allowed"] is False
    assert report["validation_case_count"] == 0

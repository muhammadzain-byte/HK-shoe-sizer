from __future__ import annotations

from pathlib import Path

from scripts.validate_measurement_accuracy import run_validation
from scripts.verify_database_readiness import verify_database_readiness


def test_database_readiness_script_runs_without_live_database_crash() -> None:
    result = verify_database_readiness("sqlite:///:memory:")

    assert result["database_ready"] is False
    assert "users" in result["expected_tables"]
    assert "users" in result["missing_tables"]


def test_database_readiness_reports_missing_db_safely(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    result = verify_database_readiness()

    assert result["database_url_present"] is False
    assert result["ready_for_validation_testing"] is False
    assert "DATABASE_URL is not set." in result["issues"]


def test_validation_harness_creates_template_when_csv_missing(tmp_path: Path) -> None:
    csv_path = tmp_path / "validation_cases.csv"
    output_dir = tmp_path / "artifacts"

    summary = run_validation(csv_path, output_dir)

    assert summary["case_count"] == 0
    assert csv_path.exists()
    assert (output_dir / "measurement_accuracy_report.csv").exists()
    assert (output_dir / "measurement_accuracy_summary.json").exists()
    assert "No accuracy claim" in " ".join(summary["notes"])

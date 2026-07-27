import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.validation_accuracy_report_service import ValidationAccuracyReportService


def test_accuracy_report_blocks_claim_under_50_cases() -> None:
    rows = [
        {
            "length_abs_error_mm": 2.0,
            "width_abs_error_mm": 1.0,
            "failure_stage": None,
            "failure_reasons_json": [],
            "pipeline_output_json": {"device_group": "Android:Chrome"},
        }
    ]

    summary = ValidationAccuracyReportService().summarize(rows)

    assert summary["completed_count"] == 1
    assert summary["mean_length_abs_error_mm"] == 2.0
    assert summary["accuracy_claim_allowed"] is False
    assert "At least 50" in summary["reason_accuracy_claim_blocked"]


def test_accuracy_report_counts_failures_and_reasons() -> None:
    rows = [
        {
            "length_abs_error_mm": None,
            "width_abs_error_mm": None,
            "failure_stage": "scale",
            "failure_reasons_json": ["Scale is unavailable."],
            "pipeline_output_json": {},
        },
        {
            "length_abs_error_mm": None,
            "width_abs_error_mm": None,
            "failure_stage": "scale",
            "failure_reasons_json": ["Scale is unavailable."],
            "pipeline_output_json": {},
        },
    ]

    summary = ValidationAccuracyReportService().summarize(rows)

    assert summary["failure_stage_counts"] == {"scale": 2}
    assert summary["common_failure_reasons"] == {"Scale is unavailable.": 2}

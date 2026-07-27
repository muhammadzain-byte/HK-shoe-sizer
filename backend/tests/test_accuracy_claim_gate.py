from app.services.validation_accuracy_report_service import ValidationAccuracyReportService


def _row(group: str, length_error: float = 2.0) -> dict:
    return {
        "length_abs_error_mm": length_error,
        "width_abs_error_mm": 1.0,
        "failure_stage": None,
        "failure_reasons_json": [],
        "pipeline_output_json": {"device_group": group},
    }


def test_accuracy_claim_gate_blocks_under_50_cases() -> None:
    summary = ValidationAccuracyReportService().summarize([_row("Android:Chrome") for _ in range(49)])

    assert summary["accuracy_claim_allowed"] is False
    assert "50" in summary["reason_accuracy_claim_blocked"]


def test_accuracy_claim_gate_blocks_fewer_than_3_device_groups() -> None:
    summary = ValidationAccuracyReportService().summarize([_row("Android:Chrome") for _ in range(50)])

    assert summary["accuracy_claim_allowed"] is False
    assert "3 device" in summary["reason_accuracy_claim_blocked"]


def test_synthetic_external_datasets_are_not_in_report_inputs() -> None:
    summary = ValidationAccuracyReportService().summarize([])

    assert summary["case_count"] == 0
    assert summary["accuracy_claim_allowed"] is False

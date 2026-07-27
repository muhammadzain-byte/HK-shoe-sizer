from __future__ import annotations

import csv
from pathlib import Path

from app.services.validation_dataset_loader import (
    REQUIRED_VALIDATION_COLUMNS,
    ValidationDatasetLoader,
)
from scripts.validate_measurement_accuracy import DEFAULT_CSV_PATH


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = columns or REQUIRED_VALIDATION_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def base_row(**overrides: str) -> dict[str, str]:
    row = {column: "" for column in REQUIRED_VALIDATION_COLUMNS}
    row.update(
        {
            "case_id": "VAL900",
            "case_label": "good_android_credit_card",
            "image_path": "images/VAL900.jpg",
            "device_label": "Android phone",
            "device_os": "Android",
            "browser": "Chrome",
            "capture_scenario": "good_capture",
            "foot_side": "right",
            "ground_truth_source": "manual_ruler",
            "reference_mode": "credit_card",
            "reference_width_mm": "85.60",
            "reference_height_mm": "53.98",
            "expected_capture_status": "ready",
            "expected_measurement_status": "trusted",
            "expected_scale_status": "available",
            "expected_recommendation_status": "recommended",
            "notes": "test row",
        }
    )
    row.update(overrides)
    return row


def test_loads_valid_csv(tmp_path: Path) -> None:
    image = tmp_path / "images" / "VAL900.jpg"
    image.parent.mkdir()
    image.write_bytes(b"not-a-real-image-but-present")
    csv_path = tmp_path / "validation_cases.csv"
    write_csv(
        csv_path,
        [
            base_row(
                image_path="images/VAL900.jpg",
                ground_truth_length_mm="240",
                ground_truth_width_mm="92",
            )
        ],
    )

    dataset = ValidationDatasetLoader(project_root=tmp_path).load_csv(csv_path)
    summary = ValidationDatasetLoader(project_root=tmp_path).summarize_dataset(dataset.rows)

    assert dataset.rows[0]["case_id"] == "VAL900"
    assert dataset.issues == []
    assert summary["real_image_count"] == 1
    assert summary["ground_truth_count"] == 1


def test_detects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    write_csv(csv_path, [{"case_id": "VAL001"}], columns=["case_id"])

    dataset = ValidationDatasetLoader(project_root=tmp_path).load_csv(csv_path)

    messages = [issue.message for issue in dataset.issues]
    assert "Missing required column: image_path" in messages


def test_allows_sample_rows_with_missing_images_but_reports_count(tmp_path: Path) -> None:
    csv_path = tmp_path / "validation_cases.csv"
    write_csv(csv_path, [base_row()])

    dataset = ValidationDatasetLoader(project_root=tmp_path).load_csv(csv_path)
    summary = ValidationDatasetLoader(project_root=tmp_path).summarize_dataset(dataset.rows)

    assert summary["case_count"] == 1
    assert summary["missing_image_count"] == 1
    assert summary["issues"][0]["severity"] == "warning"


def test_counts_scenarios(tmp_path: Path) -> None:
    csv_path = tmp_path / "validation_cases.csv"
    write_csv(
        csv_path,
        [
            base_row(case_id="VAL901", capture_scenario="good_capture"),
            base_row(case_id="VAL902", capture_scenario="low_light"),
            base_row(case_id="VAL903", capture_scenario="low_light"),
        ],
    )

    dataset = ValidationDatasetLoader(project_root=tmp_path).load_csv(csv_path)
    summary = ValidationDatasetLoader(project_root=tmp_path).summarize_dataset(dataset.rows)

    assert summary["scenario_counts"] == {"good_capture": 1, "low_light": 2}


def test_counts_reference_object_cases(tmp_path: Path) -> None:
    csv_path = tmp_path / "validation_cases.csv"
    write_csv(
        csv_path,
        [
            base_row(case_id="VAL901", reference_mode="credit_card"),
            base_row(case_id="VAL902", reference_mode="none", reference_width_mm="", reference_height_mm=""),
        ],
    )

    dataset = ValidationDatasetLoader(project_root=tmp_path).load_csv(csv_path)
    summary = ValidationDatasetLoader(project_root=tmp_path).summarize_dataset(dataset.rows)

    assert summary["reference_object_count"] == 1


def test_counts_ground_truth_cases(tmp_path: Path) -> None:
    csv_path = tmp_path / "validation_cases.csv"
    write_csv(
        csv_path,
        [
            base_row(case_id="VAL901", ground_truth_length_mm="240", ground_truth_width_mm="92"),
            base_row(case_id="VAL902"),
        ],
    )

    dataset = ValidationDatasetLoader(project_root=tmp_path).load_csv(csv_path)
    summary = ValidationDatasetLoader(project_root=tmp_path).summarize_dataset(dataset.rows)

    assert summary["ground_truth_count"] == 1


def test_rejects_invalid_reference_dimensions(tmp_path: Path) -> None:
    row = base_row(reference_width_mm="0", reference_height_mm="")

    issues = ValidationDatasetLoader(project_root=tmp_path).validate_case(row)

    assert any(issue.severity == "error" for issue in issues)
    assert any("Reference dimensions are required" in issue.message for issue in issues)


def test_validation_harness_uses_default_dataset_path() -> None:
    assert DEFAULT_CSV_PATH.as_posix().endswith("datasets/validation/validation_cases.csv")

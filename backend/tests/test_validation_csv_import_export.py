import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from scripts.import_validation_cases import import_validation_cases, row_to_payload


def test_csv_import_without_user_is_dry_run(tmp_path: Path) -> None:
    csv_path = tmp_path / "validation_cases.csv"
    csv_path.write_text(
        "case_id,case_label,image_path,device_label,device_os,browser,camera_type,foot_side,capture_scenario,"
        "ground_truth_length_mm,ground_truth_width_mm,ground_truth_source,reference_mode,reference_width_mm,"
        "reference_height_mm,reference_bbox_x,reference_bbox_y,reference_bbox_width,reference_bbox_height,"
        "reference_polygon_json,expected_status,notes\n"
        "VAL001,case,,,,Chrome,rear,right,good_capture,,,,credit_card,85.6,53.98,,,,,,draft,note\n",
        encoding="utf-8",
    )

    report = import_validation_cases(csv_path, None)

    assert report["dry_run"] is True
    assert report["skipped"] == 1


def test_row_to_payload_does_not_mark_incomplete_row_benchmark_ready() -> None:
    row = {
        "case_id": "VAL002",
        "case_label": "sample",
        "device_label": "",
        "device_os": "Android",
        "browser": "Chrome",
        "camera_type": "rear",
        "foot_side": "right",
        "capture_scenario": "good_capture",
        "ground_truth_length_mm": "",
        "ground_truth_width_mm": "",
        "ground_truth_source": "manual_ruler",
        "reference_mode": "credit_card",
        "reference_width_mm": "85.6",
        "reference_height_mm": "53.98",
        "reference_bbox_x": "",
        "reference_bbox_y": "",
        "reference_bbox_width": "",
        "reference_bbox_height": "",
        "reference_polygon_json": "",
        "notes": "template only",
    }

    payload = row_to_payload(row)

    assert payload.ground_truth_length_mm is None
    assert payload.reference_mode == "credit_card"

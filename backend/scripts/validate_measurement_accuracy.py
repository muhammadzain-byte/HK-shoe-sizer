from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from statistics import mean, median
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.validation_dataset_loader import (  # noqa: E402
    REQUIRED_VALIDATION_COLUMNS,
    ValidationDatasetLoader,
)
from app.services.validation_accuracy_report_service import ValidationAccuracyReportService  # noqa: E402

try:
    from app.db.session import SessionLocal  # noqa: E402
    from app.models.validation_benchmark_result import ValidationBenchmarkResult  # noqa: E402
except Exception:  # pragma: no cover - keeps CSV-only mode usable without DB settings.
    SessionLocal = None
    ValidationBenchmarkResult = None

DEFAULT_CSV_PATH = PROJECT_ROOT / "datasets/validation/validation_cases.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "datasets/validation/reports"
SAMPLE_TEMPLATE_PATH = PROJECT_ROOT / "datasets/validation/templates/sample_validation_cases.csv"
TEMPLATE_COLUMNS = REQUIRED_VALIDATION_COLUMNS


def run_validation(
    csv_path: Path,
    output_dir: Path,
    *,
    from_db: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "measurement_accuracy_report.csv"
    summary_path = output_dir / "measurement_accuracy_summary.json"

    if from_db:
        summary = _run_from_db(summary_path)
        _write_report(report_path, [])
        return summary

    if not csv_path.exists() or csv_path.stat().st_size == 0:
        _create_default_dataset_csv(csv_path)
        summary = _empty_summary(
            notes=[
                f"Dataset template created at {csv_path}. Fill it with real-device validation cases.",
                "Sample/template cases are not accuracy evidence.",
                "No accuracy claim can be made until ground-truth cases are provided.",
            ]
        )
        _write_report(report_path, [])
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    loader = ValidationDatasetLoader(project_root=Path.cwd())
    dataset = loader.load_csv(csv_path)
    rows = dataset.rows
    if not rows:
        summary = _empty_summary(
            notes=[
                "CSV has headers but no validation cases.",
                "Sample/template cases are not accuracy evidence.",
            ]
        )
        _write_report(report_path, [])
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    report_rows: list[dict[str, Any]] = []
    for row in rows:
        report_rows.append(_evaluate_row(row))

    trusted = [
        row for row in report_rows if row["validation_status"] == "ready_for_pipeline_measurement"
    ]
    summary = {
        "case_count": len(report_rows),
        "mean_length_error_mm": _aggregate(trusted, "length_error_mm", mean),
        "median_length_error_mm": _aggregate(trusted, "length_error_mm", median),
        "max_length_error_mm": _aggregate(trusted, "length_error_mm", max),
        "mean_width_error_mm": _aggregate(trusted, "width_error_mm", mean),
        "median_width_error_mm": _aggregate(trusted, "width_error_mm", median),
        "max_width_error_mm": _aggregate(trusted, "width_error_mm", max),
        "trusted_case_count": len(trusted),
        "rejected_case_count": len(report_rows) - len(trusted),
        "notes": [
            "This harness compares outputs against manual ground truth after pipeline measurements are available.",
            "Rows without complete ground truth or reference bbox remain rejected from accuracy statistics.",
            "Sample/template cases are not accuracy evidence.",
        ],
        "dataset_summary": loader.summarize_dataset(rows),
    }
    _write_report(report_path, report_rows)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _evaluate_row(row: dict[str, str]) -> dict[str, Any]:
    length_truth = _float(row.get("ground_truth_length_mm") or row.get("foot_length_mm_ground_truth"))
    width_truth = _float(row.get("ground_truth_width_mm") or row.get("foot_width_mm_ground_truth"))
    reference_width = _float(row.get("reference_width_mm"))
    reference_height = _float(row.get("reference_height_mm"))
    bbox_width = _float(row.get("reference_bbox_width"))
    bbox_height = _float(row.get("reference_bbox_height"))
    issues: list[str] = []

    if not row.get("image_path"):
        issues.append("image_path is required.")
    if length_truth is None or width_truth is None:
        issues.append("Manual ground-truth length and width are required.")
    if reference_width is None or reference_height is None or bbox_width is None or bbox_height is None:
        issues.append("Reference object dimensions and bbox are required for real-world scale.")

    # The real measurement pipeline is intentionally not faked here. This row is marked as
    # ready only when the data needed to run a trusted pipeline is present.
    status = "ready_for_pipeline_measurement" if not issues else "needs_data"
    return {
        "image_path": row.get("image_path", ""),
        "validation_status": status,
        "ground_truth_length_mm": length_truth,
        "ground_truth_width_mm": width_truth,
        "ai_length_mm": None,
        "ai_width_mm": None,
        "length_error_mm": None,
        "width_error_mm": None,
        "length_percent_error": None,
        "width_percent_error": None,
        "issues": "; ".join(issues),
        "notes": row.get("notes", ""),
    }


def _write_template(csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_COLUMNS)
        writer.writeheader()


def _create_default_dataset_csv(csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if SAMPLE_TEMPLATE_PATH.exists():
        shutil.copyfile(SAMPLE_TEMPLATE_PATH, csv_path)
        return
    _write_template(csv_path)


def _write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "image_path",
        "validation_status",
        "ground_truth_length_mm",
        "ground_truth_width_mm",
        "ai_length_mm",
        "ai_width_mm",
        "length_error_mm",
        "width_error_mm",
        "length_percent_error",
        "width_percent_error",
        "issues",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _empty_summary(notes: list[str]) -> dict[str, Any]:
    return {
        "case_count": 0,
        "mean_length_error_mm": None,
        "median_length_error_mm": None,
        "max_length_error_mm": None,
        "mean_width_error_mm": None,
        "median_width_error_mm": None,
        "max_width_error_mm": None,
        "trusted_case_count": 0,
        "rejected_case_count": 0,
        "notes": notes,
    }


def _aggregate(rows: list[dict[str, Any]], key: str, fn) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(float(fn(values)), 4) if values else None


def _float(value: str | None) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except ValueError:
        return None


def _run_from_db(summary_path: Path) -> dict[str, Any]:
    if SessionLocal is None or ValidationBenchmarkResult is None:
        summary = _empty_summary(["Database benchmark result mode is unavailable in this environment."])
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
    with SessionLocal() as db:
        results = list(db.query(ValidationBenchmarkResult).all())
    summary = ValidationAccuracyReportService().summarize(results)
    summary["notes"] = [
        "Summary is based on validation_benchmark_results table.",
        "External synthetic/research datasets are not real-device accuracy evidence.",
        "Production accuracy claims remain blocked until documented benchmark thresholds are met.",
    ]
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate AI foot measurements against manual ground truth.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV_PATH), help="Validation case CSV path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--from-db", action="store_true", help="Summarize validation_benchmark_results table.")
    args = parser.parse_args()
    summary = run_validation(Path(args.csv), Path(args.output_dir), from_db=args.from_db)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

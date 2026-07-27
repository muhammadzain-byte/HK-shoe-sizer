from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.validation_benchmark_result import ValidationBenchmarkResult  # noqa: E402
from app.models.validation_case import ValidationCase  # noqa: E402
from app.services.validation_accuracy_report_service import ValidationAccuracyReportService  # noqa: E402
from app.services.validation_benchmark_service import ValidationBenchmarkService  # noqa: E402


REPORT_FIELDS = [
    "validation_case_id",
    "scan_id",
    "measured_length_mm",
    "measured_width_mm",
    "ground_truth_length_mm",
    "ground_truth_width_mm",
    "length_error_mm",
    "width_error_mm",
    "length_abs_error_mm",
    "width_abs_error_mm",
    "length_error_percent",
    "width_error_percent",
    "capture_status",
    "measurement_status",
    "scale_status",
    "size_status",
    "failure_stage",
    "failure_reasons",
]


def run_validation_benchmark(*, case_id: str | None = None, status_filter: str | None = None) -> dict:
    reports_dir = ROOT / "datasets" / "validation" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        statement = select(ValidationCase)
        if case_id:
            statement = statement.where(ValidationCase.case_id == case_id)
        if status_filter:
            statement = statement.where(ValidationCase.status == status_filter)
        cases = list(db.scalars(statement))
        service = ValidationBenchmarkService(db)
        results: list[ValidationBenchmarkResult] = []
        for case in cases:
            user = db.get(User, case.user_id)
            if user:
                results.append(service.run_case_benchmark(user, case.id))
        summary = ValidationAccuracyReportService().summarize(results)

    csv_path = reports_dir / "validation_benchmark_report.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "validation_case_id": result.validation_case_id,
                    "scan_id": result.scan_id or "",
                    "measured_length_mm": result.measured_length_mm or "",
                    "measured_width_mm": result.measured_width_mm or "",
                    "ground_truth_length_mm": result.ground_truth_length_mm or "",
                    "ground_truth_width_mm": result.ground_truth_width_mm or "",
                    "length_error_mm": result.length_error_mm or "",
                    "width_error_mm": result.width_error_mm or "",
                    "length_abs_error_mm": result.length_abs_error_mm or "",
                    "width_abs_error_mm": result.width_abs_error_mm or "",
                    "length_error_percent": result.length_error_percent or "",
                    "width_error_percent": result.width_error_percent or "",
                    "capture_status": result.capture_status or "",
                    "measurement_status": result.measurement_status or "",
                    "scale_status": result.scale_status or "",
                    "size_status": result.size_status or "",
                    "failure_stage": result.failure_stage or "",
                    "failure_reasons": "; ".join(result.failure_reasons_json or []),
                }
            )
    summary_path = reports_dir / "validation_benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {"cases_run": len(results), "report_csv": str(csv_path), "summary_json": str(summary_path), "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real-device validation benchmarks.")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--status", default=None)
    args = parser.parse_args()
    report = run_validation_benchmark(case_id=args.case_id, status_filter=args.status)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

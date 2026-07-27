from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models.validation_benchmark_result import ValidationBenchmarkResult  # noqa: E402
from app.models.validation_case import ValidationCase  # noqa: E402
from app.services.validation_accuracy_report_service import ValidationAccuracyReportService  # noqa: E402
from scripts.verify_database_readiness import verify_database_readiness  # noqa: E402


def export_testing_report() -> dict:
    readiness = verify_database_readiness() if os.environ.get("DATABASE_URL") else {
        "ready_for_validation_testing": False,
        "issues": ["DATABASE_URL is not set."],
    }
    case_count = benchmark_ready_count = completed_count = 0
    accuracy_summary = ValidationAccuracyReportService().summarize([])
    if os.environ.get("DATABASE_URL") and readiness.get("ready_for_validation_testing"):
        with SessionLocal() as db:
            cases = list(db.scalars(select(ValidationCase)))
            results = list(db.scalars(select(ValidationBenchmarkResult)))
        case_count = len(cases)
        benchmark_ready_count = sum(1 for case in cases if case.status == "benchmark_ready")
        completed_count = sum(1 for case in cases if case.status == "benchmark_completed")
        accuracy_summary = ValidationAccuracyReportService().summarize(results)

    report = {
        "db_ready": bool(readiness.get("ready_for_validation_testing")),
        "migration_status": readiness.get("alembic_current_revision"),
        "validation_case_count": case_count,
        "benchmark_ready_count": benchmark_ready_count,
        "completed_benchmark_count": completed_count,
        "accuracy_claim_allowed": accuracy_summary["accuracy_claim_allowed"],
        "reason_blocked": accuracy_summary["reason_accuracy_claim_blocked"],
        "next_steps": _next_steps(readiness, case_count),
    }
    output = ROOT / "datasets" / "validation" / "reports" / "testing_readiness_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["output_path"] = str(output)
    return report


def _next_steps(readiness: dict, case_count: int) -> list[str]:
    if not readiness.get("ready_for_validation_testing"):
        return ["Start the testing database, set DATABASE_URL, and run backend/scripts/apply_migrations.py."]
    if case_count == 0:
        return ["Open /validation and create the first real validation case."]
    return ["Continue collecting real-device validation cases until at least 50 completed benchmarks exist."]


def main() -> int:
    report = export_testing_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

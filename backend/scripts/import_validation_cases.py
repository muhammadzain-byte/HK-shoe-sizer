from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.validation_case import ValidationCaseCreate  # noqa: E402
from app.services.validation_case_service import ValidationCaseService  # noqa: E402


VALIDATION_CASE_COLUMNS = [
    "case_id",
    "case_label",
    "image_path",
    "device_label",
    "device_os",
    "browser",
    "camera_type",
    "foot_side",
    "capture_scenario",
    "ground_truth_length_mm",
    "ground_truth_width_mm",
    "ground_truth_source",
    "reference_mode",
    "reference_width_mm",
    "reference_height_mm",
    "reference_bbox_x",
    "reference_bbox_y",
    "reference_bbox_width",
    "reference_bbox_height",
    "reference_polygon_json",
    "expected_status",
    "notes",
]


def row_to_payload(row: dict[str, str]) -> ValidationCaseCreate:
    polygon = None
    if row.get("reference_polygon_json"):
        polygon = json.loads(row["reference_polygon_json"])
    return ValidationCaseCreate(
        case_id=row["case_id"],
        case_label=row.get("case_label") or None,
        device_label=row.get("device_label") or None,
        device_os=row.get("device_os") or None,
        browser=row.get("browser") or None,
        camera_type=row.get("camera_type") or None,
        foot_side=row.get("foot_side") or "unknown",
        capture_scenario=row.get("capture_scenario") or None,
        ground_truth_length_mm=_float_or_none(row.get("ground_truth_length_mm")),
        ground_truth_width_mm=_float_or_none(row.get("ground_truth_width_mm")),
        ground_truth_source=row.get("ground_truth_source") or None,
        reference_mode=row.get("reference_mode") or "none",
        reference_width_mm=_float_or_none(row.get("reference_width_mm")),
        reference_height_mm=_float_or_none(row.get("reference_height_mm")),
        reference_bbox_x=_float_or_none(row.get("reference_bbox_x")),
        reference_bbox_y=_float_or_none(row.get("reference_bbox_y")),
        reference_bbox_width=_float_or_none(row.get("reference_bbox_width")),
        reference_bbox_height=_float_or_none(row.get("reference_bbox_height")),
        reference_polygon_json=polygon,
        notes=row.get("notes") or None,
    )


def import_validation_cases(csv_path: Path, user_id: UUID | None, dry_run: bool = False) -> dict:
    if not csv_path.exists():
        return {"imported": 0, "dry_run": dry_run, "issues": [f"CSV not found: {csv_path}"]}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in VALIDATION_CASE_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            return {"imported": 0, "dry_run": dry_run, "issues": [f"Missing columns: {', '.join(missing)}"]}
        rows = list(reader)

    report = {"imported": 0, "dry_run": dry_run or user_id is None, "issues": [], "skipped": 0}
    if dry_run or user_id is None:
        report["issues"].append("No database writes were made. Provide --user-id to import records.")
        report["skipped"] = len(rows)
        return report

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return {"imported": 0, "dry_run": False, "issues": [f"User not found: {user_id}"], "skipped": len(rows)}
        service = ValidationCaseService(db)
        for row in rows:
            try:
                service.create_case(user, row_to_payload(row))
                report["imported"] += 1
            except Exception as exc:
                report["skipped"] += 1
                report["issues"].append(f"{row.get('case_id', 'unknown')}: {exc}")
    return report


def _float_or_none(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import real-device validation cases from CSV.")
    parser.add_argument("--csv", default=str(ROOT / "datasets" / "validation" / "validation_cases.csv"))
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = import_validation_cases(
        Path(args.csv),
        UUID(args.user_id) if args.user_id else None,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))
    return 0 if not report["issues"] or report["dry_run"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

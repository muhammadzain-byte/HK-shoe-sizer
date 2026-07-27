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

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.validation_case import ValidationCase  # noqa: E402

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


def export_validation_cases(output_path: Path, user_id: UUID | None = None) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        statement = select(ValidationCase)
        if user_id:
            statement = statement.where(ValidationCase.user_id == user_id)
        cases = list(db.scalars(statement.order_by(ValidationCase.created_at.desc())))
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=VALIDATION_CASE_COLUMNS)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case.case_id,
                    "case_label": case.case_label or "",
                    "image_path": "",
                    "device_label": case.device_label or "",
                    "device_os": case.device_os or "",
                    "browser": case.browser or "",
                    "camera_type": case.camera_type or "",
                    "foot_side": case.foot_side or "",
                    "capture_scenario": case.capture_scenario or "",
                    "ground_truth_length_mm": case.ground_truth_length_mm or "",
                    "ground_truth_width_mm": case.ground_truth_width_mm or "",
                    "ground_truth_source": case.ground_truth_source or "",
                    "reference_mode": case.reference_mode,
                    "reference_width_mm": case.reference_width_mm or "",
                    "reference_height_mm": case.reference_height_mm or "",
                    "reference_bbox_x": case.reference_bbox_x or "",
                    "reference_bbox_y": case.reference_bbox_y or "",
                    "reference_bbox_width": case.reference_bbox_width or "",
                    "reference_bbox_height": case.reference_bbox_height or "",
                    "reference_polygon_json": json.dumps(case.reference_polygon_json or ""),
                    "expected_status": case.status,
                    "notes": case.notes or "",
                }
            )
    return {"exported": len(cases), "output": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export validation cases to CSV.")
    parser.add_argument("--output", default=str(ROOT / "datasets" / "validation" / "validation_cases_export.csv"))
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()
    report = export_validation_cases(Path(args.output), UUID(args.user_id) if args.user_id else None)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

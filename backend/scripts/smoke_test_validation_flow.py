from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models.foot_scan import FootScan  # noqa: E402
from app.models.uploaded_image import UploadedImage  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.validation_case import ValidationCaseCreate  # noqa: E402
from app.services.validation_benchmark_service import ValidationBenchmarkService  # noqa: E402
from app.services.validation_case_service import ValidationCaseService  # noqa: E402
from scripts.verify_database_readiness import verify_database_readiness  # noqa: E402


def smoke_test_validation_flow() -> dict:
    if not os.environ.get("DATABASE_URL"):
        return {
            "db_ready": False,
            "validation_case_created": False,
            "ground_truth_saved": False,
            "incomplete_case_blocked": False,
            "reference_annotation_saved": False,
            "summary_ok": False,
            "benchmark_ready_gate_tested": False,
            "benchmark_run": False,
            "benchmark_blocker": "DATABASE_URL is not set.",
            "cleanup_ok": True,
            "ready_for_manual_real_device_testing": False,
        }
    readiness = verify_database_readiness()
    if not readiness.get("ready_for_validation_testing"):
        return {
            "db_ready": False,
            "validation_case_created": False,
            "ground_truth_saved": False,
            "incomplete_case_blocked": False,
            "reference_annotation_saved": False,
            "summary_ok": False,
            "benchmark_ready_gate_tested": False,
            "benchmark_run": False,
            "benchmark_blocker": "; ".join(readiness.get("issues", [])),
            "cleanup_ok": True,
            "ready_for_manual_real_device_testing": False,
        }

    created = []
    result = {
        "db_ready": True,
        "validation_case_created": False,
        "ground_truth_saved": False,
        "incomplete_case_blocked": False,
        "reference_annotation_saved": False,
        "summary_ok": False,
        "benchmark_ready_gate_tested": False,
        "benchmark_run": False,
        "benchmark_blocker": None,
        "cleanup_ok": False,
        "ready_for_manual_real_device_testing": False,
    }
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "validation-smoke@example.test"))
            if not user:
                user = User(
                    email="validation-smoke@example.test",
                    password_hash="smoke-only",
                    first_name="Validation",
                    last_name="Smoke",
                    gender="woman",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                created.append(user)

            service = ValidationCaseService(db)
            case = service.create_case(
                user,
                ValidationCaseCreate(
                    case_id=f"SMOKE-{uuid4().hex[:8]}",
                    case_label="smoke validation case",
                    ground_truth_length_mm=240.0,
                    ground_truth_width_mm=92.0,
                    ground_truth_source="manual_ruler",
                    reference_mode="credit_card",
                    reference_width_mm=85.6,
                    reference_height_mm=53.98,
                    reference_bbox_x=10,
                    reference_bbox_y=10,
                    reference_bbox_width=160,
                    reference_bbox_height=100,
                    foot_side="right",
                    capture_scenario="smoke",
                ),
            )
            created.append(case)
            result["validation_case_created"] = True
            result["ground_truth_saved"] = True
            result["reference_annotation_saved"] = True
            summary = service.summary(user)
            result["summary_ok"] = summary["total"] >= 1
            try:
                service.mark_benchmark_ready(user, case.id)
            except Exception:
                result["incomplete_case_blocked"] = True

            scan = FootScan(user_id=user.id, foot_side="right", status="image_uploaded")
            db.add(scan)
            db.flush()
            created.append(scan)
            image = UploadedImage(
                user_id=user.id,
                foot_scan_id=scan.id,
                bucket="local",
                object_key="smoke-placeholder.jpg",
                content_type="image/jpeg",
                byte_size=1,
                upload_status="uploaded",
            )
            db.add(image)
            db.flush()
            created.append(image)
            case.scan_id = scan.id
            case.image_upload_id = image.id
            db.commit()
            service.mark_benchmark_ready(user, case.id)
            result["benchmark_ready_gate_tested"] = True
            benchmark = ValidationBenchmarkService(db).run_case_benchmark(user, case.id)
            result["benchmark_run"] = benchmark.failure_stage is None
            result["benchmark_blocker"] = benchmark.failure_stage or None
            result["ready_for_manual_real_device_testing"] = True
            for item in reversed(created):
                db.delete(item)
            db.commit()
            result["cleanup_ok"] = True
    except Exception as exc:
        result["benchmark_blocker"] = str(exc)
    return result


def main() -> int:
    report = smoke_test_validation_flow()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_manual_real_device_testing"] or not report["db_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

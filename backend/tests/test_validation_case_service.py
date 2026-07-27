import os
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.models.validation_case import ValidationCase
from app.services.validation_case_service import ValidationCaseService


def test_benchmark_ready_requires_image_ground_truth_scan_and_reference() -> None:
    case = ValidationCase(
        id=uuid4(),
        user_id=uuid4(),
        case_id="VAL001",
        reference_mode="credit_card",
    )

    issues = ValidationCaseService(None).benchmark_readiness_issues(case)  # type: ignore[arg-type]

    assert "A real uploaded image is required." in issues
    assert "Manual ground-truth length and width in millimeters are required." in issues
    assert "A linked scan is required before benchmark execution." in issues
    assert "Reference object dimensions and bbox/polygon are required." in issues


def test_benchmark_ready_accepts_complete_reference_case() -> None:
    case = ValidationCase(
        id=uuid4(),
        user_id=uuid4(),
        case_id="VAL002",
        image_upload_id=uuid4(),
        scan_id=uuid4(),
        ground_truth_length_mm=240.0,
        ground_truth_width_mm=92.0,
        reference_mode="credit_card",
        reference_width_mm=85.6,
        reference_height_mm=53.98,
        reference_bbox_x=10,
        reference_bbox_y=20,
        reference_bbox_width=160,
        reference_bbox_height=100,
    )

    issues = ValidationCaseService(None).benchmark_readiness_issues(case)  # type: ignore[arg-type]

    assert issues == []

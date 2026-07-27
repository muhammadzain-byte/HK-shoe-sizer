from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.pipeline import FullPipelineRequest
from app.schemas.shoe_size import ShoeSizeRequest
from app.services.scan_orchestration_service import ScanOrchestrationService


def reference_object() -> dict:
    return {
        "type": "credit_card",
        "known_width_mm": 85.6,
        "known_height_mm": 53.98,
        "bbox": {"x": 0, "y": 0, "width": 856, "height": 539.8},
        "detection_confidence": 0.95,
        "same_plane_confidence": 0.98,
    }


def user():
    return SimpleNamespace(id=uuid4())


def scan(owner_id):
    return SimpleNamespace(id=uuid4(), user_id=owner_id)


def image(owner_id, scan_id):
    return SimpleNamespace(id=uuid4(), user_id=owner_id, foot_scan_id=scan_id, upload_status="uploaded")


def capture(owner_id, scan_id, status="ready"):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        foot_scan_id=scan_id,
        capture_status=status,
        capture_quality_score=0.94 if status == "ready" else 0.2,
        issues=["bad_capture"] if status == "reject" else [],
        primary_instruction="Show the full heel." if status == "reject" else None,
    )


def measurement(scan_id, status="trusted"):
    return SimpleNamespace(
        id=uuid4(),
        scan_id=scan_id,
        measurement_status=status,
        foot_length_pixels=2420.0,
        foot_width_pixels=900.0,
    )


class FakeDb:
    def __init__(self, scalar_values):
        self.scalar_values = list(scalar_values)
        self.added = []
        self.committed = False

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, value) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()


def service_with_records(capture_status="ready", measurement_status="trusted"):
    current_user = user()
    current_scan = scan(current_user.id)
    records = [
        current_scan,
        image(current_user.id, current_scan.id),
        capture(current_user.id, current_scan.id, capture_status),
        measurement(current_scan.id, measurement_status),
    ]
    return current_user, current_scan, ScanOrchestrationService(FakeDb(records))


def test_bad_capture_blocks_pipeline() -> None:
    current_user, current_scan, service = service_with_records(capture_status="reject")

    result = service.run_full_pipeline(current_user, current_scan.id, FullPipelineRequest())

    assert result.overall_status == "capture_needs_adjustment"
    assert result.measurement.stage_status == "not_run"
    assert "Retake photo" in result.next_action


def test_measurement_failed_quality_gate_blocks_scale_and_size() -> None:
    current_user, current_scan, service = service_with_records(measurement_status="failed_quality_gate")

    result = service.run_full_pipeline(current_user, current_scan.id, FullPipelineRequest())

    assert result.overall_status == "measurement_needs_review"
    assert result.scale_estimate.stage_status == "not_run"


def test_scale_unavailable_blocks_size() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(current_user, current_scan.id, FullPipelineRequest())

    assert result.overall_status == "scale_unavailable"
    assert result.shoe_recommendation is None


def test_reference_object_scale_can_allow_ready_for_size() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(
        current_user,
        current_scan.id,
        FullPipelineRequest(reference_object=reference_object()),
    )

    assert result.overall_status == "ready_for_size"
    assert result.scale_estimate.stage_status == "passed"


def test_trusted_measurement_available_scale_and_size_request_returns_recommendation() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(
        current_user,
        current_scan.id,
        FullPipelineRequest(
            reference_object=reference_object(),
            run_shoe_size=True,
            shoe_size_request=ShoeSizeRequest(
                region="EU",
                gender="women",
                fit_preference="regular",
                shoe_type="flat",
            ),
        ),
    )

    assert result.overall_status == "size_recommended"
    assert result.shoe_recommendation is not None
    assert result.shoe_recommendation.recommendation_status == "recommended"


def test_no_shoe_size_when_run_shoe_size_false() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(
        current_user,
        current_scan.id,
        FullPipelineRequest(reference_object=reference_object(), run_shoe_size=False),
    )

    assert result.overall_status == "ready_for_size"
    assert result.shoe_recommendation is None


def test_user_cannot_run_pipeline_on_another_users_scan() -> None:
    db = FakeDb([None])

    with pytest.raises(HTTPException) as exc:
        ScanOrchestrationService(db).run_full_pipeline(user(), uuid4(), FullPipelineRequest())

    assert exc.value.status_code == 404


def test_pipeline_returns_clear_next_action() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(current_user, current_scan.id, FullPipelineRequest())

    assert result.next_action == "Use a reference object or supported depth mode for real-world scale."
    assert result.user_message == "Scale is unavailable, so shoe size is blocked."

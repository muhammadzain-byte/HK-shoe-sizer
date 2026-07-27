from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.schemas.pipeline import FullPipelineRequest
from app.schemas.reference_object import ReferenceObjectDetectionOptions
from app.services.reference_object_detection_service import ReferenceObjectDetectionService
from app.services.scale_estimation_service import ScaleEstimationService
from app.services.scan_orchestration_service import ScanOrchestrationService


def trusted_measurement() -> dict:
    return {
        "measurement_status": "trusted",
        "foot_length_pixels": 2500.0,
        "foot_width_pixels": 940.0,
    }


def manual_detection_options(with_bbox: bool = True) -> ReferenceObjectDetectionOptions:
    return ReferenceObjectDetectionOptions(
        enabled=True,
        reference_mode="credit_card",
        manual_bbox=(
            {"x": 30, "y": 30, "width": 856.0, "height": 539.8}
            if with_bbox
            else None
        ),
        detection_confidence=0.95,
        same_plane_confidence=0.95,
    )


def test_valid_reference_object_can_produce_scale() -> None:
    detection = ReferenceObjectDetectionService().detect_reference_object(
        reference_mode="credit_card",
        manual_bbox={"x": 30, "y": 30, "width": 856.0, "height": 539.8},
        detection_confidence=0.95,
        same_plane_confidence=0.95,
    )

    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        reference_object=detection.reference_object,
    )

    assert detection.detected is True
    assert result.scale_status == "available"
    assert result.real_world_measurement.foot_length_mm == 250.0


def test_scale_unavailable_when_reference_detection_fails() -> None:
    detection = ReferenceObjectDetectionService().detect_reference_object(reference_mode="credit_card")

    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        reference_object=detection.reference_object,
    )

    assert detection.detected is False
    assert result.scale_status == "unavailable"


def user():
    return SimpleNamespace(id=uuid4())


def scan(owner_id):
    return SimpleNamespace(id=uuid4(), user_id=owner_id)


def image(owner_id, scan_id):
    return SimpleNamespace(id=uuid4(), user_id=owner_id, foot_scan_id=scan_id, upload_status="uploaded")


def capture(owner_id, scan_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        foot_scan_id=scan_id,
        capture_status="ready",
        capture_quality_score=0.94,
        issues=[],
        primary_instruction=None,
    )


def measurement(scan_id):
    return SimpleNamespace(
        id=uuid4(),
        scan_id=scan_id,
        measurement_status="trusted",
        foot_length_pixels=2500.0,
        foot_width_pixels=940.0,
    )


class FakeDb:
    def __init__(self, scalar_values):
        self.scalar_values = list(scalar_values)
        self.added = []

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        return None

    def refresh(self, value) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()


def service_with_records():
    current_user = user()
    current_scan = scan(current_user.id)
    records = [
        current_scan,
        image(current_user.id, current_scan.id),
        capture(current_user.id, current_scan.id),
        measurement(current_scan.id),
    ]
    return current_user, current_scan, ScanOrchestrationService(FakeDb(records))


def test_full_pipeline_blocks_size_when_reference_object_missing() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(
        current_user,
        current_scan.id,
        FullPipelineRequest(
            reference_object_detection=manual_detection_options(with_bbox=False),
            run_shoe_size=True,
        ),
    )

    assert result.overall_status == "scale_unavailable"
    assert result.shoe_recommendation is None
    assert result.scale_estimate.data["scale_status"] == "needs_reference"


def test_full_pipeline_can_reach_ready_for_size_with_valid_reference_scale() -> None:
    current_user, current_scan, service = service_with_records()

    result = service.run_full_pipeline(
        current_user,
        current_scan.id,
        FullPipelineRequest(reference_object_detection=manual_detection_options()),
    )

    assert result.overall_status == "ready_for_size"
    assert result.scale_estimate.stage_status == "passed"

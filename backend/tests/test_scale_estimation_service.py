from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.scale_estimate import ScaleEstimate
from app.services.scale_estimate_persistence_service import ScaleEstimatePersistenceService
from app.services.scale_estimation_service import ScaleEstimationService


def trusted_measurement() -> dict:
    return {
        "measurement_status": "trusted",
        "foot_length_pixels": 2500.0,
        "foot_width_pixels": 940.0,
        "heel_point": {"x": 120, "y": 520},
        "toe_point": {"x": 125, "y": 20},
        "width_points": {
            "left": {"x": 80, "y": 220},
            "right": {"x": 180, "y": 220},
        },
    }


def reference_object(confidence: float = 0.95) -> dict:
    return {
        "type": "credit_card",
        "known_width_mm": 85.6,
        "known_height_mm": 53.98,
        "bbox": {"x": 20, "y": 20, "width": 856.0, "height": 539.8},
        "detection_confidence": confidence,
        "same_plane_confidence": 0.98,
    }


def test_no_scale_source_returns_unavailable() -> None:
    result = ScaleEstimationService().estimate_scale(trusted_measurement())

    assert result.scale_status == "unavailable"
    assert result.scale_mode == "unavailable"
    assert result.mm_per_pixel is None
    assert result.real_world_measurement.foot_length_mm is None


def test_measurement_not_trusted_blocks_scale() -> None:
    measurement = {**trusted_measurement(), "measurement_status": "needs_review"}

    result = ScaleEstimationService().estimate_scale(measurement, reference_object=reference_object())

    assert result.scale_status == "unavailable"
    assert "Measurement must be trusted before scale can be estimated." in result.issues
    assert result.real_world_measurement.foot_width_mm is None


def test_reference_object_with_known_dimensions_returns_available_scale() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        reference_object=reference_object(),
    )

    assert result.scale_status == "available"
    assert result.scale_mode == "reference_object"
    assert result.pixels_per_mm == 10.0
    assert result.mm_per_pixel == 0.1
    assert result.confidence >= 0.85


def test_low_confidence_reference_object_returns_low_confidence() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        reference_object=reference_object(confidence=0.4),
    )

    assert result.scale_status == "low_confidence"
    assert result.mm_per_pixel is None
    assert "Reference object detection confidence is too low." in result.issues


def test_inconsistent_width_height_scale_returns_low_confidence() -> None:
    distorted = reference_object()
    distorted["bbox"] = {"x": 20, "y": 20, "width": 856.0, "height": 340.0}

    result = ScaleEstimationService().estimate_scale(trusted_measurement(), reference_object=distorted)

    assert result.scale_status == "low_confidence"
    assert result.evidence["scale_consistency"] < 0.85
    assert result.real_world_measurement.foot_length_mm is None


def test_device_metadata_alone_returns_unavailable() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        device_metadata={"device_family": "iPhone", "video_width": 1920, "video_height": 1080},
    )

    assert result.scale_status == "unavailable"
    assert result.scale_mode == "device_camera_model"
    assert "Device metadata alone is not a trusted scale source." in result.issues


def test_monocular_depth_without_calibration_returns_unavailable() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        depth_metadata={
            "depth_available": True,
            "depth_mode": "monocular",
            "depth_confidence": 0.9,
            "plane_confidence": 0.9,
            "calibrated": False,
        },
    )

    assert result.scale_status == "unavailable"
    assert result.scale_mode == "monocular_depth_model"
    assert "Monocular depth is not calibrated for millimeter conversion." in result.issues


def test_low_confidence_depth_returns_low_confidence() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        depth_metadata={
            "depth_available": True,
            "depth_mode": "arcore",
            "depth_confidence": 0.5,
            "plane_confidence": 0.9,
        },
    )

    assert result.scale_status == "low_confidence"
    assert result.scale_mode == "ar_depth"
    assert result.mm_per_pixel is None


def test_available_scale_converts_pixel_length_and_width_to_mm() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        reference_object=reference_object(),
    )

    assert result.real_world_measurement.foot_length_mm == 250.0
    assert result.real_world_measurement.foot_width_mm == 94.0
    assert result.real_world_measurement.can_recommend_size is False


def test_scale_unavailable_keeps_mm_values_null() -> None:
    result = ScaleEstimationService().estimate_scale(trusted_measurement())

    assert result.real_world_measurement.foot_length_mm is None
    assert result.real_world_measurement.foot_width_mm is None
    assert result.real_world_measurement.can_recommend_size is False


class FakeDb:
    def __init__(self, scalar_value=None) -> None:
        self.scalar_value = scalar_value
        self.added = None
        self.committed = False
        self.refreshed = None

    def add(self, value) -> None:
        self.added = value

    def commit(self) -> None:
        self.committed = True

    def refresh(self, value) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        if getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(UTC)
        self.refreshed = value

    def scalar(self, _statement):
        return self.scalar_value


def test_scale_estimate_is_persisted() -> None:
    user = SimpleNamespace(id=uuid4())
    scan_id = uuid4()
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        reference_object=reference_object(),
    )
    db = FakeDb()

    record = ScaleEstimatePersistenceService(db).persist_estimate(user, scan_id, result)

    assert db.added is record
    assert db.committed is True
    assert record.user_id == user.id
    assert record.foot_scan_id == scan_id
    assert record.scale_status == "available"
    assert record.foot_length_mm == 250.0
    assert record.can_recommend_size is False


def test_user_cannot_access_another_users_scale_estimate() -> None:
    user = SimpleNamespace(id=uuid4())
    db = FakeDb(scalar_value=None)

    with pytest.raises(HTTPException) as exc:
        ScaleEstimatePersistenceService(db).get_scale_estimate(user, uuid4())

    assert exc.value.status_code == 404


def test_scale_estimate_model_can_store_blocking_reason() -> None:
    estimate = ScaleEstimate(
        user_id=uuid4(),
        foot_scan_id=uuid4(),
        scale_status="unavailable",
        scale_mode="unavailable",
        confidence=0.0,
        issues=["No trusted scale source was provided."],
        instructions=["Use a reference object."],
        can_recommend_size=False,
    )

    assert estimate.foot_length_mm is None
    assert estimate.can_recommend_size is False

from pathlib import Path

import numpy as np
from PIL import Image

from app.services.measurement_service import MeasurementService


def make_synthetic_foot_mask() -> np.ndarray:
    mask = np.zeros((220, 140), dtype=bool)
    yy, xx = np.ogrid[:220, :140]
    lower = ((xx - 70) ** 2 / 34**2 + (yy - 142) ** 2 / 70**2) <= 1
    toe = ((xx - 70) ** 2 / 44**2 + (yy - 55) ** 2 / 34**2) <= 1
    bridge = (xx >= 38) & (xx <= 102) & (yy >= 55) & (yy <= 145)
    mask[lower | toe | bridge] = True
    return mask


def test_measurement_engine_generates_points_and_dimensions() -> None:
    service = MeasurementService()
    result = service.measure_mask(make_synthetic_foot_mask(), segmentation_confidence=0.92)

    assert result.measurement_status == "completed"
    assert result.foot_length_pixels > 120
    assert result.foot_width_pixels > 60
    assert result.heel_point.y > result.toe_point.y
    assert result.legacy is not None
    assert result.heel_point != result.legacy.heel_point
    assert result.width_left_point.x != result.width_right_point.x
    assert abs(result.width_left_point.y - result.width_right_point.y) < result.foot_width_pixels
    assert 0 < result.confidence_score <= 0.99


def test_measurement_prefers_refined_heel_center() -> None:
    service = MeasurementService()
    result = service.measure_mask(
        make_synthetic_foot_mask(),
        segmentation_confidence=0.92,
        refinement_metadata={
            "heel_boundary_confidence": 0.81,
            "heel_center": {"x": 70.0, "y": 196.0},
        },
    )

    assert result.heel_point.x == 70.0
    assert result.heel_point.y == 196.0
    assert "heel center fallback used" not in result.quality_issues


def test_measurement_reports_heel_center_fallback() -> None:
    service = MeasurementService()
    result = service.measure_mask(
        make_synthetic_foot_mask(),
        segmentation_confidence=0.92,
        refinement_metadata={
            "heel_boundary_confidence": 0.20,
            "heel_center": {"x": 70.0, "y": 196.0},
        },
    )

    assert "heel center fallback used" in result.quality_issues


def test_measurement_overlay_is_created(tmp_path: Path) -> None:
    service = MeasurementService()
    result = service.measure_mask(make_synthetic_foot_mask(), segmentation_confidence=0.92)
    image = Image.new("RGB", (140, 220), "white")
    output = tmp_path / "measurement_overlay.png"

    service.save_overlay(image, result, output)
    comparison = tmp_path / "measurement_comparison_overlay.png"
    service.save_comparison_overlay(image, result, comparison)

    assert output.exists()
    assert output.stat().st_size > 0
    assert comparison.exists()
    assert comparison.stat().st_size > 0


def test_measurement_persistence_creates_database_record() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.added = None
            self.committed = False
            self.refreshed = None

        def add(self, value) -> None:
            self.added = value

        def commit(self) -> None:
            self.committed = True

        def refresh(self, value) -> None:
            self.refreshed = value

    service = MeasurementService()
    result = service.measure_mask(make_synthetic_foot_mask(), segmentation_confidence=0.92)
    session = FakeSession()

    measurement = service.persist_result(session, "00000000-0000-0000-0000-000000000001", result)

    assert session.added is measurement
    assert session.committed is True
    assert session.refreshed is measurement
    assert measurement.measurement_status == "completed"
    assert measurement.foot_length_pixels is not None
    assert measurement.foot_width_pixels is not None

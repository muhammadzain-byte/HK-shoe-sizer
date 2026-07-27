from __future__ import annotations

import numpy as np

from app.services.reference_object_detection_service import ReferenceObjectDetectionService


def service() -> ReferenceObjectDetectionService:
    return ReferenceObjectDetectionService()


def test_missing_reference_object_returns_needs_reference() -> None:
    result = service().detect_reference_object(reference_mode="credit_card")

    assert result.detected is False
    assert "Reference object bbox or polygon is required." in result.issues


def test_manual_credit_card_bbox_returns_valid_reference_input() -> None:
    result = service().detect_reference_object(
        reference_mode="credit_card",
        manual_bbox={"x": 20, "y": 20, "width": 856.0, "height": 539.8},
        detection_confidence=0.95,
        same_plane_confidence=0.9,
    )

    assert result.detected is True
    assert result.reference_object is not None
    assert result.reference_object["known_width_mm"] == 85.6
    assert result.reference_object["bbox"]["width"] == 856.0


def test_low_confidence_reference_object_is_rejected() -> None:
    result = service().detect_reference_object(
        reference_mode="credit_card",
        manual_bbox={"x": 20, "y": 20, "width": 856.0, "height": 539.8},
        detection_confidence=0.4,
        same_plane_confidence=0.9,
    )

    assert result.detected is False
    assert "Reference object detection confidence is too low." in result.issues


def test_distorted_reference_object_is_low_confidence() -> None:
    result = service().detect_reference_object(
        reference_mode="credit_card",
        manual_bbox={"x": 20, "y": 20, "width": 856.0, "height": 539.8},
        manual_polygon=[
            {"x": 20, "y": 20},
            {"x": 876, "y": 20},
            {"x": 400, "y": 560},
            {"x": 20, "y": 560},
        ],
        detection_confidence=0.95,
        same_plane_confidence=0.9,
    )

    assert result.detected is False
    assert "Reference object is too distorted for trusted scale." in result.issues


def test_reference_object_overlapping_foot_is_rejected() -> None:
    foot_mask = np.zeros((200, 200), dtype=np.uint8)
    foot_mask[40:120, 40:120] = 255

    result = service().detect_reference_object(
        reference_mode="credit_card",
        manual_bbox={"x": 50, "y": 50, "width": 70.0, "height": 44.0},
        detection_confidence=0.95,
        same_plane_confidence=0.9,
        foot_mask=foot_mask,
    )

    assert result.detected is False
    assert "Reference object overlaps the foot mask." in result.issues

from __future__ import annotations

from dataclasses import replace

import numpy as np
from PIL import Image

from app.services.ai.contracts import BoundingBox
from app.services.ai.foot_region_refinement_service import FootRegionRefinementService
from app.services.anatomical_landmark_validator import AnatomicalLandmarkValidator
from app.services.measurement_service import MeasurementPoint, MeasurementService


def make_foot_only_mask() -> np.ndarray:
    mask = np.zeros((340, 190), dtype=bool)
    yy, xx = np.ogrid[:340, :190]
    for center_x, radius_x, radius_y in (
        (55, 15, 22),
        (76, 14, 24),
        (98, 15, 26),
        (122, 16, 28),
        (148, 20, 32),
    ):
        toe = ((xx - center_x) ** 2 / radius_x**2 + (yy - 54) ** 2 / radius_y**2) <= 1
        mask[toe] = True
    forefoot = ((xx - 100) ** 2 / 68**2 + (yy - 112) ** 2 / 48**2) <= 1
    midfoot = ((xx - 94) ** 2 / 45**2 + (yy - 180) ** 2 / 66**2) <= 1
    heel = ((xx - 92) ** 2 / 42**2 + (yy - 258) ** 2 / 42**2) <= 1
    bridge = (xx >= 50) & (xx <= 138) & (yy >= 110) & (yy <= 250)
    mask[forefoot | midfoot | heel | bridge] = True
    return mask


def make_foot_with_lower_leg_mask() -> np.ndarray:
    mask = make_foot_only_mask()
    yy, xx = np.ogrid[:340, :190]
    leg = ((xx - 92) ** 2 / 31**2) <= 1
    mask[(yy >= 248) & leg] = True
    return mask


def bbox(mask: np.ndarray) -> BoundingBox:
    ys, xs = np.where(mask)
    return BoundingBox(
        x=int(xs.min()),
        y=int(ys.min()),
        width=int(xs.max() - xs.min() + 1),
        height=int(ys.max() - ys.min() + 1),
    )


def validated_result(mask: np.ndarray, metadata: dict | None = None):
    measurement = MeasurementService().measure_mask(mask, 0.92, refinement_metadata=metadata)
    return AnatomicalLandmarkValidator().validate(
        original_image=Image.new("RGB", (mask.shape[1], mask.shape[0]), "white"),
        selected_candidate_mask=None,
        refined_foot_mask=mask,
        heel_boundary_metadata=metadata,
        measurement_result=measurement,
        width_profile=metadata.get("width_profile") if metadata else None,
        contour_points=measurement.contour_points,
    )


def refined_fixture():
    selected_mask = make_foot_with_lower_leg_mask()
    refinement = FootRegionRefinementService().refine(selected_mask, bbox(selected_mask))
    metadata = refinement.to_metadata()
    measurement = MeasurementService().measure_mask(refinement.refined_mask, 0.92, metadata)
    validator = AnatomicalLandmarkValidator()
    return selected_mask, refinement.refined_mask, metadata, measurement, validator


class LowRiskValidator(AnatomicalLandmarkValidator):
    def _validate_toe_point(self, *args, **kwargs):
        return 0.96, [], {"top_crop_risk": 0.2, "near_top_bbox_edge": False}

    def _validate_heel_center(self, *args, **kwargs):
        return 0.97, [], {"heel_boundary_evidence": "contour_supported"}

    def _validate_heel_boundary(self, *args, **kwargs):
        return 0.96, [], {
            "heel_boundary_type": "curved",
            "heel_boundary_confidence": 0.95,
            "removed_lower_leg_area_ratio": 0.18,
        }

    def _validate_forefoot_width(self, *args, **kwargs):
        return 0.95, [], {"axial_position": 0.42}

    def _validate_mask_quality(self, *args, **kwargs):
        return 0.96, [], {
            "components": 1,
            "hole_ratio": 0.0,
            "solidity": 0.94,
            "completeness": 0.92,
            "rectangularity": 0.55,
            "lower_leg_risk": 0.2,
            "top_crop_risk": 0.2,
        }


def test_high_top_crop_risk_never_returns_trusted() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()

    report = validator.validate(None, selected_mask, refined_mask, metadata, measurement)

    assert report.measurement_status == "failed_quality_gate"
    assert report.trusted is False
    assert report.risk_scores["top_crop_risk"] >= 0.75
    assert "top_crop_risk_fail" in report.hard_gates_triggered
    assert report.penalties["top_crop_penalty"] == 0.25


def test_heel_center_inside_lower_leg_fails() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()
    bad_measurement = replace(measurement, heel_point=MeasurementPoint(92, 330))

    report = validator.validate(None, selected_mask, refined_mask, metadata, bad_measurement)

    assert report.measurement_status == "failed_quality_gate"
    assert any("heel center" in issue for issue in report.issues)


def test_toe_point_outside_toe_region_fails() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()
    bad_measurement = replace(measurement, toe_point=MeasurementPoint(10, 320))

    report = validator.validate(None, selected_mask, refined_mask, metadata, bad_measurement)

    assert report.measurement_status == "failed_quality_gate"
    assert any("toe point" in issue for issue in report.issues)


def test_width_line_in_midfoot_fails() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()
    bad_measurement = replace(
        measurement,
        width_left_point=MeasurementPoint(55, 185),
        width_right_point=MeasurementPoint(132, 185),
    )

    report = validator.validate(None, selected_mask, refined_mask, metadata, bad_measurement)

    assert report.landmark_scores["forefoot_width"] < 0.70
    assert report.measurement_status in {"needs_review", "failed_quality_gate"}


def test_width_line_in_heel_region_fails() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()
    bad_measurement = replace(
        measurement,
        width_left_point=MeasurementPoint(58, 265),
        width_right_point=MeasurementPoint(126, 265),
    )

    report = validator.validate(None, selected_mask, refined_mask, metadata, bad_measurement)

    assert report.landmark_scores["forefoot_width"] < 0.70
    assert report.measurement_status in {"needs_review", "failed_quality_gate"}


def test_refined_mask_with_lower_leg_included_fails() -> None:
    mask = make_foot_with_lower_leg_mask()
    metadata = {
        "heel_boundary_type": "straight_fallback",
        "heel_boundary_confidence": 0.3,
        "removed_lower_leg_area_ratio": 0.0,
        "heel_center": {"x": 92, "y": 330},
        "width_profile": [],
    }

    report = validated_result(mask, metadata)

    assert report.measurement_status == "failed_quality_gate"
    assert any("lower-leg" in issue for issue in report.issues)
    assert report.trusted is False


def test_high_lower_leg_risk_should_never_return_trusted() -> None:
    mask = np.zeros((340, 190), dtype=bool)
    mask[30:330, 60:128] = True
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.7,
        "removed_lower_leg_area_ratio": 0.02,
        "heel_center": {"x": 94, "y": 320},
        "heel_curve_points": [{"x": x, "y": 320} for x in range(60, 130, 10)],
    }

    report = validated_result(mask, metadata)

    assert report.trusted is False
    assert report.risk_scores["lower_leg_risk"] >= 0.60
    assert "lower_leg_risk" in ",".join(report.hard_gates_triggered)


def test_high_lower_leg_and_top_crop_risk_cannot_be_trusted() -> None:
    mask = np.zeros((340, 190), dtype=bool)
    mask[30:330, 48:140] = True
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.7,
        "removed_lower_leg_area_ratio": 0.02,
        "heel_center": {"x": 94, "y": 320},
        "heel_curve_points": [{"x": x, "y": 320} for x in range(60, 130, 10)],
    }

    report = validated_result(mask, metadata)

    assert report.measurement_status in {"needs_review", "failed_quality_gate"}
    assert report.trusted is False
    assert any("combined_lower_leg_and_top_crop" in gate for gate in report.hard_gates_triggered)


def test_overtrimmed_heel_fails() -> None:
    mask = make_foot_only_mask()
    mask[255:, :] = False
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.5,
        "removed_lower_leg_area_ratio": 0.55,
        "heel_center": {"x": 92, "y": 254},
        "heel_curve_points": [{"x": x, "y": 254} for x in range(55, 130, 10)],
    }

    report = validated_result(mask, metadata)

    assert report.measurement_status == "failed_quality_gate"
    assert any("over-trimmed" in issue or "posterior" in issue for issue in report.issues)


def test_straight_fallback_heel_reduces_confidence() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()
    fallback = {
        **metadata,
        "heel_boundary_type": "straight_fallback",
        "heel_boundary_confidence": 0.48,
        "heel_curve_points": [],
    }

    curved_report = validator.validate(None, selected_mask, refined_mask, metadata, measurement)
    fallback_report = validator.validate(None, selected_mask, refined_mask, fallback, measurement)

    assert fallback_report.trust_score_after_penalties < curved_report.trust_score_after_penalties
    assert fallback_report.penalties["heel_penalty"] >= 0.10
    assert "minor: straight heel boundary fallback reduces trust" in fallback_report.issues


def test_toe_point_on_top_bbox_edge_reduces_toe_score() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()

    report = validator.validate(None, selected_mask, refined_mask, metadata, measurement)

    assert report.landmark_scores["toe_point"] < 1.0
    assert any("Toe point may be constrained by crop boundary." in issue for issue in report.issues)


def test_rectangular_mask_reduces_mask_quality() -> None:
    mask = np.zeros((260, 160), dtype=bool)
    mask[20:240, 35:125] = True
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.8,
        "removed_lower_leg_area_ratio": 0.18,
        "heel_center": {"x": 80, "y": 238},
        "heel_curve_points": [{"x": x, "y": 238} for x in range(45, 120, 10)],
    }

    report = validated_result(mask, metadata)

    assert report.risk_scores["rectangularity"] >= 0.75
    assert report.penalties["rectangularity_penalty"] > 0
    assert report.trusted is False


def test_low_completeness_reduces_trust_score() -> None:
    mask = make_foot_only_mask()
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.9,
        "removed_lower_leg_area_ratio": 0.18,
        "heel_center": {"x": 92, "y": 295},
        "heel_curve_points": [{"x": x, "y": 295} for x in range(55, 130, 10)],
        "heel_boundary_evidence": "contour_supported",
    }

    report = validated_result(mask, metadata)

    assert report.risk_scores["completeness"] < 0.85
    assert report.penalties["completeness_penalty"] > 0
    assert report.trust_score_after_penalties < report.trust_score_raw


def test_good_landmarks_but_high_risk_signals_still_need_review_or_fail() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()

    report = validator.validate(None, selected_mask, refined_mask, metadata, measurement)

    assert min(report.landmark_scores.values()) >= 0.70
    assert report.measurement_status in {"needs_review", "failed_quality_gate"}
    assert report.trusted is False


def test_low_risk_good_landmarks_can_return_trusted() -> None:
    _selected_mask, refined_mask, metadata, measurement, _validator = refined_fixture()
    metadata = {**metadata, "heel_boundary_evidence": "contour_supported"}

    report = LowRiskValidator().validate(None, refined_mask, refined_mask, metadata, measurement)

    assert report.measurement_status == "trusted"
    assert report.trusted is True
    assert report.trust_score_after_penalties >= 0.90
    assert report.hard_gates_triggered == []


def test_risk_penalties_appear_in_quality_report_payload() -> None:
    selected_mask, refined_mask, metadata, measurement, validator = refined_fixture()

    report = validator.validate(None, selected_mask, refined_mask, metadata, measurement)
    payload = report.to_dict()

    assert "trust_score_raw" in payload
    assert "trust_score_after_penalties" in payload
    assert "risk_scores" in payload
    assert "penalties" in payload
    assert "hard_gates_triggered" in payload
    assert "recommendation_reason" in payload
    assert payload["penalties"]["top_crop_penalty"] > 0


def test_missing_toes_fails() -> None:
    mask = make_foot_only_mask()
    mask[:85, :] = False
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.8,
        "removed_lower_leg_area_ratio": 0.18,
        "heel_center": {"x": 92, "y": 295},
        "heel_curve_points": [{"x": x, "y": 295} for x in range(55, 130, 10)],
    }

    report = validated_result(mask, metadata)

    assert report.measurement_status == "failed_quality_gate"
    assert report.landmark_scores["toe_point"] < 0.70


def test_large_holes_or_disconnected_artifacts_fail() -> None:
    mask = make_foot_only_mask()
    mask[120:165, 72:118] = False
    mask[10:25, 10:25] = True
    metadata = {
        "heel_boundary_type": "curved",
        "heel_boundary_confidence": 0.8,
        "removed_lower_leg_area_ratio": 0.18,
        "heel_center": {"x": 92, "y": 295},
        "heel_curve_points": [{"x": x, "y": 295} for x in range(55, 130, 10)],
    }

    report = validated_result(mask, metadata)

    assert report.measurement_status == "failed_quality_gate"
    assert any("holes" in issue or "disconnected" in issue for issue in report.issues)

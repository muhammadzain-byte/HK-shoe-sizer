import numpy as np

from app.services.ai.contracts import BoundingBox
from app.services.ai.foot_region_refinement_service import FootRegionRefinementService


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


def make_missing_heel_mask() -> np.ndarray:
    mask = make_foot_only_mask()
    mask[225:, :] = False
    return mask


def make_cylindrical_mask() -> np.ndarray:
    mask = np.zeros((340, 190), dtype=bool)
    yy, xx = np.ogrid[:340, :190]
    cylinder = ((xx - 96) ** 2 / 35**2) <= 1
    mask[(yy >= 35) & (yy <= 320) & cylinder] = True
    return mask


def bbox(mask: np.ndarray) -> BoundingBox:
    ys, xs = np.where(mask)
    return BoundingBox(
        x=int(xs.min()),
        y=int(ys.min()),
        width=int(xs.max() - xs.min() + 1),
        height=int(ys.max() - ys.min() + 1),
    )


def test_refinement_trims_lower_leg_continuation() -> None:
    mask = make_foot_with_lower_leg_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))

    assert result.refined_bbox.height <= result.original_bbox.height
    assert result.removed_lower_leg_area_ratio > 0.04
    assert result.refinement_confidence >= 0.45
    assert result.heel_boundary_type == "curved"
    assert result.heel_boundary_confidence >= 0.60
    assert result.heel_curve_points
    assert result.refined_mask[:145, :].sum() > 0
    assert result.refined_mask[145:230, :].sum() > 0
    assert result.refined_mask[240:295, :].sum() > 0
    assert result.refined_mask[300:, :].sum() < mask[300:, :].sum() * 0.4


def test_refinement_does_not_overtrim_foot_only_mask() -> None:
    mask = make_foot_only_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))

    assert result.refined_mask.sum() >= mask.sum() * 0.90
    assert result.removed_lower_leg_area_ratio < 0.10
    assert result.heel_boundary_type == "straight_fallback"
    assert result.refined_mask[:145, :].sum() > 0
    assert result.refined_mask[220:, :].sum() > 0


def test_flat_fallback_is_reported_when_curve_is_not_clear() -> None:
    mask = make_foot_only_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))
    metadata = result.to_metadata()

    assert metadata["heel_boundary_type"] == "straight_fallback"
    assert metadata["heel_boundary_confidence"] <= 0.58
    assert metadata["heel_curve_points"] == []


def test_refinement_warns_when_heel_is_missing() -> None:
    mask = make_missing_heel_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))

    assert result.refinement_confidence <= 0.58
    assert result.issues
    assert result.heel_boundary_type == "straight_fallback"


def test_refinement_low_confidence_without_toe_forefoot_pattern() -> None:
    mask = make_cylindrical_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))

    assert result.refinement_confidence <= 0.58
    assert result.issues
    assert result.heel_boundary_type == "straight_fallback"


def test_refined_bbox_is_not_larger_than_original() -> None:
    mask = make_foot_with_lower_leg_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))

    assert result.refined_bbox.width <= result.original_bbox.width
    assert result.refined_bbox.height <= result.original_bbox.height


def test_heel_center_stays_out_of_lower_leg_region() -> None:
    mask = make_foot_with_lower_leg_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))
    metadata = result.to_metadata()

    assert metadata["heel_center"]["y"] < 305
    assert metadata["heel_center"]["y"] <= result.refined_bbox.y + result.refined_bbox.height
    assert metadata["ankle_transition_position"] < 0.95


def test_refined_mask_preserves_toes_forefoot_and_heel() -> None:
    mask = make_foot_with_lower_leg_mask()
    service = FootRegionRefinementService()

    result = service.refine(mask, bbox(mask))

    assert result.refined_mask[35:85, :].sum() > mask[35:85, :].sum() * 0.90
    assert result.refined_mask[90:160, :].sum() > mask[90:160, :].sum() * 0.90
    assert result.refined_mask[230:290, :].sum() > 0

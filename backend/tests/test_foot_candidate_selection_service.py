import numpy as np

from app.services.ai.foot_candidate_selection_service import FootCandidateSelectionService


def make_synthetic_anatomical_foot() -> np.ndarray:
    mask = np.zeros((260, 180), dtype=bool)
    yy, xx = np.ogrid[:260, :180]

    toe_centers = [48, 70, 92, 114, 136]
    toe_radii = [(18, 23), (15, 21), (14, 19), (13, 18), (12, 16)]
    for center_x, (radius_x, radius_y) in zip(toe_centers, toe_radii, strict=True):
        toe = ((xx - center_x) ** 2 / radius_x**2 + (yy - 42) ** 2 / radius_y**2) <= 1
        mask[toe] = True

    forefoot = ((xx - 91) ** 2 / 68**2 + (yy - 92) ** 2 / 42**2) <= 1
    midfoot = ((xx - 88) ** 2 / 44**2 + (yy - 150) ** 2 / 54**2) <= 1
    heel = ((xx - 86) ** 2 / 36**2 + (yy - 213) ** 2 / 38**2) <= 1
    bridge = (xx >= 46) & (xx <= 126) & (yy >= 90) & (yy <= 205)
    mask[forefoot | midfoot | heel | bridge] = True
    return mask


def make_cylindrical_leg_region() -> np.ndarray:
    mask = np.zeros((260, 180), dtype=bool)
    yy, xx = np.ogrid[:260, :180]
    leg = ((xx - 92) ** 2 / 35**2) <= 1
    mask[(yy >= 80) & leg] = True
    return mask


def test_selector_prefers_full_foot_over_lower_leg_candidate() -> None:
    selector = FootCandidateSelectionService()

    result = selector.select(
        [
            {"mask": make_cylindrical_leg_region(), "score": 0.99},
            {"mask": make_synthetic_anatomical_foot(), "score": 0.88},
        ],
        image_size=(180, 260),
    )

    assert result.selected is not None
    selected = result.selected.diagnostics
    assert selected is not None
    assert selected["source_index"] == 1
    assert selected["toe_score"] >= 0.42
    assert selected["forefoot_score"] >= 0.34
    assert selected["leg_rejection_score"] < 0.62

    leg_candidates = [
        candidate
        for candidate in result.candidates
        if candidate.source_index == 0 and candidate.source in {"sam_mask", "component"}
    ]
    assert leg_candidates
    assert all(candidate.rejected for candidate in leg_candidates)
    assert any("cylindrical" in (candidate.rejection_reason or "") for candidate in leg_candidates)

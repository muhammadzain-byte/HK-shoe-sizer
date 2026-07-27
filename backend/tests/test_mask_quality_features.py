from __future__ import annotations

import numpy as np

from app.research.mask_quality.features import (
    extract_mask_quality_features,
    generate_synthetic_negatives,
)


def fake_mask() -> np.ndarray:
    mask = np.zeros((80, 40), dtype=np.uint8)
    mask[8:70, 12:28] = 255
    mask[8:18, 8:32] = 255
    return mask


def test_mask_quality_feature_extraction_works() -> None:
    features = extract_mask_quality_features(fake_mask())

    assert features["area_ratio"] > 0
    assert features["bbox_aspect_ratio"] > 1
    assert features["component_count"] == 1


def test_synthetic_negative_mask_generation_works() -> None:
    negatives = generate_synthetic_negatives(fake_mask())

    assert {label for label, _mask in negatives} >= {"cropped", "rectangular", "holey"}

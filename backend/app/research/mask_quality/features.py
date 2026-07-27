from __future__ import annotations

from typing import Any

import cv2
import numpy as np


FEATURE_NAMES = [
    "area_ratio",
    "bbox_aspect_ratio",
    "solidity",
    "rectangularity",
    "contour_point_count",
    "width_profile_mean",
    "width_profile_std",
    "lower_leg_risk_proxy",
    "top_crop_risk_proxy",
    "hole_ratio",
    "component_count",
    "toe_region_complexity_proxy",
]


def extract_mask_quality_features(mask: np.ndarray) -> dict[str, float]:
    binary = (mask > 0).astype(np.uint8)
    area = int(np.count_nonzero(binary))
    image_area = max(int(binary.size), 1)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or area == 0:
        return {name: 0.0 for name in FEATURE_NAMES}
    contour = max(contours, key=cv2.contourArea)
    x, y, width, height = cv2.boundingRect(contour)
    bbox_area = max(width * height, 1)
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    profile = _width_profile(binary, y, height)
    component_count, _labels = cv2.connectedComponents(binary)
    holes = _hole_ratio(binary, area)
    return {
        "area_ratio": area / image_area,
        "bbox_aspect_ratio": height / max(width, 1),
        "solidity": min(area / hull_area, 1.0),
        "rectangularity": area / bbox_area,
        "contour_point_count": float(len(contour)),
        "width_profile_mean": float(np.mean(profile)) if profile else 0.0,
        "width_profile_std": float(np.std(profile)) if profile else 0.0,
        "lower_leg_risk_proxy": _lower_leg_risk(profile),
        "top_crop_risk_proxy": 1.0 if y <= 2 else 0.0,
        "hole_ratio": holes,
        "component_count": float(max(component_count - 1, 0)),
        "toe_region_complexity_proxy": _toe_complexity(profile),
    }


def feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]


def generate_synthetic_negatives(mask: np.ndarray) -> list[tuple[str, np.ndarray]]:
    binary = ((mask > 0) * 255).astype(np.uint8)
    negatives: list[tuple[str, np.ndarray]] = []
    h, w = binary.shape[:2]
    negatives.append(("cropped", _crop_top(binary, max(1, h // 5))))
    negatives.append(("cropped", _crop_bottom(binary, max(1, h // 5))))
    rectangular = np.zeros_like(binary)
    ys, xs = np.where(binary > 0)
    if len(xs) > 0:
        cv2.rectangle(rectangular, (int(xs.min()), int(ys.min())), (int(xs.max()), int(ys.max())), 255, -1)
    negatives.append(("rectangular", rectangular))
    holey = binary.copy()
    cv2.circle(holey, (w // 2, h // 2), max(2, min(h, w) // 10), 0, -1)
    negatives.append(("holey", holey))
    fragmented = binary.copy()
    fragmented[:, w // 2 : w // 2 + max(1, w // 20)] = 0
    negatives.append(("fragmented", fragmented))
    lower_leg = cv2.dilate(binary, np.ones((max(3, h // 10), 3), dtype=np.uint8), iterations=1)
    negatives.append(("lower_leg_like", lower_leg))
    return negatives


def _width_profile(binary: np.ndarray, y: int, height: int, bands: int = 20) -> list[float]:
    values: list[float] = []
    for idx in range(bands):
        y0 = y + int(idx * height / bands)
        y1 = y + int((idx + 1) * height / bands)
        band = binary[y0:max(y1, y0 + 1), :]
        xs = np.where(np.any(band > 0, axis=0))[0]
        values.append(float(len(xs)) / max(binary.shape[1], 1))
    return values


def _lower_leg_risk(profile: list[float]) -> float:
    if len(profile) < 6:
        return 0.0
    lower = profile[-5:]
    return float(1.0 - min(np.std(lower) * 10.0, 1.0))


def _toe_complexity(profile: list[float]) -> float:
    if len(profile) < 6:
        return 0.0
    top = profile[:5]
    return float(min(np.std(top) * 10.0, 1.0))


def _hole_ratio(binary: np.ndarray, area: int) -> float:
    flood = binary.copy()
    h, w = flood.shape[:2]
    mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    return float(np.count_nonzero(holes)) / max(area, 1)


def _crop_top(mask: np.ndarray, pixels: int) -> np.ndarray:
    result = mask.copy()
    result[:pixels, :] = 0
    return result


def _crop_bottom(mask: np.ndarray, pixels: int) -> np.ndarray:
    result = mask.copy()
    result[-pixels:, :] = 0
    return result


def schema_payload() -> dict[str, Any]:
    return {"features": FEATURE_NAMES, "research_only": True}

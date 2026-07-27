from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class RenderResult:
    image: np.ndarray
    mask: np.ndarray
    issues: list[str]


def render_top_down(points: np.ndarray, image_size: tuple[int, int] = (256, 128), seed: int | None = None) -> RenderResult:
    rng = np.random.default_rng(seed)
    height, width = image_size
    issues: list[str] = []
    if points.shape[0] < 3:
        return RenderResult(_blank_rgb(height, width), np.zeros((height, width), dtype=np.uint8), ["Not enough points to render."])
    projected = _project_points(points, height, width)
    if projected.shape[0] < 3:
        return RenderResult(_blank_rgb(height, width), np.zeros((height, width), dtype=np.uint8), ["Projection produced too few points."])
    hull = cv2.convexHull(projected.astype(np.int32))
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillConvexPoly(mask, hull, 255)
    mask = _smooth_mask(mask)
    image = rgb_from_mask(mask, rng)
    return RenderResult(image=image, mask=mask, issues=issues)


def rgb_from_mask(mask: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    h, w = mask.shape[:2]
    image = np.full((h, w, 3), (232, 229, 222), dtype=np.uint8)
    foot_color = np.array([190, 148, 121], dtype=np.int16)
    noise = rng.normal(0, 5, size=(h, w, 1)).astype(np.int16)
    shaded = np.clip(foot_color.reshape(1, 1, 3) + noise, 0, 255).astype(np.uint8)
    image[mask > 0] = shaded[mask > 0]
    contour, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contour, -1, (122, 92, 76), 1)
    return image


def _project_points(points: np.ndarray, height: int, width: int) -> np.ndarray:
    xy = points[:, :2].astype(np.float32)
    if np.ptp(xy[:, 0]) < np.ptp(xy[:, 1]):
        x = xy[:, 0]
        y = xy[:, 1]
    else:
        x = xy[:, 1]
        y = xy[:, 0]
    x = _normalize_axis(x, margin=14, extent=width)
    y = _normalize_axis(y, margin=18, extent=height)
    return np.column_stack([x, y]).astype(np.float32)


def _normalize_axis(values: np.ndarray, margin: int, extent: int) -> np.ndarray:
    min_value = float(np.min(values))
    max_value = float(np.max(values))
    span = max(max_value - min_value, 1e-6)
    return ((values - min_value) / span) * max(extent - 2 * margin, 1) + margin


def _smooth_mask(mask: np.ndarray) -> np.ndarray:
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    return ((mask > 80) * 255).astype(np.uint8)


def _blank_rgb(height: int, width: int) -> np.ndarray:
    return np.full((height, width, 3), (232, 229, 222), dtype=np.uint8)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class CalibrationCardEvidence:
    marker_confidence: float
    corner_markers_detected: int
    perspective_consistency: float
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_confidence": self.marker_confidence,
            "corner_markers_detected": self.corner_markers_detected,
            "perspective_consistency": self.perspective_consistency,
            "issues": self.issues,
        }


class CalibrationCardService:
    """Verifies the four high-contrast corner markers on our 100 x 60 mm card."""

    width_mm = 100.0
    height_mm = 60.0
    minimum_marker_confidence = 0.90

    def inspect(self, image: np.ndarray, polygon: list[dict[str, float]] | None) -> CalibrationCardEvidence:
        if image.ndim != 3 or image.shape[2] != 3 or not polygon or len(polygon) != 4:
            return CalibrationCardEvidence(0.0, 0, 0.0, ["Calibration card corners are unavailable."])

        points = np.array([[point["x"], point["y"]] for point in polygon], dtype=np.float32)
        ordered = self._order_points(points)
        target = np.array([[0, 0], [999, 0], [999, 599], [0, 599]], dtype=np.float32)
        transform = cv2.getPerspectiveTransform(ordered, target)
        warped = cv2.warpPerspective(image, transform, (1000, 600))
        gray = cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY)
        marker_boxes = [(28, 28), (872, 28), (872, 472), (28, 472)]
        detected = 0
        darkness: list[float] = []
        for x, y in marker_boxes:
            patch = gray[y : y + 100, x : x + 100]
            dark_ratio = float(np.mean(patch < 70))
            darkness.append(dark_ratio)
            if dark_ratio >= 0.35:
                detected += 1
        consistency = min(darkness) / max(max(darkness), 1e-6)
        confidence = round(min(1.0, (detected / 4.0) * 0.8 + consistency * 0.2), 4)
        issues = [] if confidence >= self.minimum_marker_confidence else [
            "Calibration card markers are incomplete or not clearly visible."
        ]
        return CalibrationCardEvidence(confidence, detected, round(consistency, 4), issues)

    @staticmethod
    def _order_points(points: np.ndarray) -> np.ndarray:
        ordered = np.zeros((4, 2), dtype=np.float32)
        sums = points.sum(axis=1)
        deltas = np.diff(points, axis=1).reshape(-1)
        ordered[0] = points[np.argmin(sums)]
        ordered[2] = points[np.argmax(sums)]
        ordered[1] = points[np.argmin(deltas)]
        ordered[3] = points[np.argmax(deltas)]
        return ordered

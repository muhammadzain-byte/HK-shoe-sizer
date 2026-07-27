import cv2
import numpy as np

from app.services.calibration_card_service import CalibrationCardService


def calibration_card(markers: int = 4) -> np.ndarray:
    image = np.full((600, 1000, 3), 245, dtype=np.uint8)
    for index, (x, y) in enumerate([(28, 28), (872, 28), (872, 472), (28, 472)]):
        if index < markers:
            cv2.rectangle(image, (x, y), (x + 100, y + 100), (0, 0, 0), -1)
    return image


def polygon() -> list[dict[str, float]]:
    return [{"x": 0, "y": 0}, {"x": 999, "y": 0}, {"x": 999, "y": 599}, {"x": 0, "y": 599}]


def test_full_calibration_card_has_strong_marker_evidence() -> None:
    result = CalibrationCardService().inspect(calibration_card(), polygon())
    assert result.corner_markers_detected == 4
    assert result.marker_confidence >= 0.90


def test_missing_marker_does_not_pass_calibration_card_validation() -> None:
    result = CalibrationCardService().inspect(calibration_card(markers=3), polygon())
    assert result.marker_confidence < 0.90
    assert result.issues

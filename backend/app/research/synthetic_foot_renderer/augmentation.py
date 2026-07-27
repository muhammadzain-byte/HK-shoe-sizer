from __future__ import annotations

import cv2
import numpy as np


QUALITY_LABELS = [
    "valid",
    "toe_cropped",
    "heel_cropped",
    "lower_leg_like_extension",
    "rectangular_crop",
    "fragmented",
    "holey",
    "over_dilated",
    "over_eroded",
    "off_center",
    "too_close",
    "too_far",
    "tilted",
    "partial_side_crop",
]


def augment_mask(mask: np.ndarray, label: str, rng: np.random.Generator | None = None) -> tuple[np.ndarray, list[str]]:
    rng = rng or np.random.default_rng(0)
    binary = ((mask > 0) * 255).astype(np.uint8)
    h, w = binary.shape[:2]
    if label == "valid":
        return binary, []
    if label == "toe_cropped":
        result = binary.copy()
        result[: max(4, h // 6), :] = 0
        return result, ["crop_top_toe_region"]
    if label == "heel_cropped":
        result = binary.copy()
        result[-max(4, h // 6) :, :] = 0
        return result, ["crop_bottom_heel_region"]
    if label == "lower_leg_like_extension":
        return _lower_leg_extension(binary), ["add_lower_leg_like_extension"]
    if label == "rectangular_crop":
        return _rectangle_from_bbox(binary), ["replace_with_bbox_rectangle"]
    if label == "fragmented":
        result = binary.copy()
        result[:, w // 2 : w // 2 + max(2, w // 18)] = 0
        return result, ["split_mask_fragment"]
    if label == "holey":
        result = binary.copy()
        cv2.circle(result, (w // 2, h // 2), max(5, min(h, w) // 8), 0, -1)
        return result, ["add_large_hole"]
    if label == "over_dilated":
        return cv2.dilate(binary, np.ones((9, 9), dtype=np.uint8), iterations=2), ["strong_dilation"]
    if label == "over_eroded":
        return cv2.erode(binary, np.ones((7, 7), dtype=np.uint8), iterations=2), ["strong_erosion"]
    if label == "off_center":
        shift = int(rng.choice([-1, 1]) * max(10, w // 4))
        return _translate(binary, shift, 0), ["translate_off_center"]
    if label == "too_close":
        return _scale(binary, 1.35), ["scale_too_close"]
    if label == "too_far":
        return _scale(binary, 0.62), ["scale_too_far"]
    if label == "tilted":
        return _rotate(binary, float(rng.choice([-18, -14, 14, 18]))), ["rotate_tilted"]
    if label == "partial_side_crop":
        result = binary.copy()
        if rng.random() < 0.5:
            result[:, : max(4, w // 5)] = 0
        else:
            result[:, -max(4, w // 5) :] = 0
        return result, ["crop_side_region"]
    return binary, [f"unknown_label_{label}"]


def _lower_leg_extension(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape[:2]
    result = mask.copy()
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return result
    x_center = int(np.median(xs))
    y_bottom = int(np.max(ys))
    width = max(8, int((np.max(xs) - np.min(xs)) * 0.32))
    cv2.rectangle(result, (x_center - width // 2, y_bottom - 2), (x_center + width // 2, h - 1), 255, -1)
    return result


def _rectangle_from_bbox(mask: np.ndarray) -> np.ndarray:
    result = np.zeros_like(mask)
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return result
    cv2.rectangle(result, (int(xs.min()), int(ys.min())), (int(xs.max()), int(ys.max())), 255, -1)
    return result


def _translate(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(mask, matrix, (mask.shape[1], mask.shape[0]), borderValue=0)


def _scale(mask: np.ndarray, scale: float) -> np.ndarray:
    h, w = mask.shape[:2]
    resized = cv2.resize(mask, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_NEAREST)
    result = np.zeros_like(mask)
    y0 = max((h - resized.shape[0]) // 2, 0)
    x0 = max((w - resized.shape[1]) // 2, 0)
    y1 = min(y0 + resized.shape[0], h)
    x1 = min(x0 + resized.shape[1], w)
    result[y0:y1, x0:x1] = resized[: y1 - y0, : x1 - x0]
    return result


def _rotate(mask: np.ndarray, angle: float) -> np.ndarray:
    h, w = mask.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.services.calibration_card_service import CalibrationCardService


@dataclass(frozen=True)
class ReferenceObjectDetectionResult:
    detected: bool
    reference_mode: str
    bbox: dict[str, float] | None = None
    polygon: list[dict[str, float]] | None = None
    confidence: float = 0.0
    distortion_score: float = 1.0
    same_plane_confidence: float = 0.0
    source: str = "manual"
    reference_object: dict[str, Any] | None = None
    issues: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "reference_mode": self.reference_mode,
            "bbox": self.bbox,
            "polygon": self.polygon,
            "confidence": self.confidence,
            "distortion_score": self.distortion_score,
            "same_plane_confidence": self.same_plane_confidence,
            "source": self.source,
            "reference_object": self.reference_object,
            "issues": self.issues,
            "instructions": self.instructions,
        }


class ReferenceObjectDetectionService:
    """Detects or validates reference objects without pretending scale evidence exists."""

    known_dimensions_mm = {
        "credit_card": (85.60, 53.98),
        "a4_paper": (210.0, 297.0),
        "calibration_card": (CalibrationCardService.width_mm, CalibrationCardService.height_mm),
    }
    minimum_detection_confidence = 0.85
    maximum_distortion_score = 0.25
    minimum_same_plane_confidence = 0.75
    edge_margin_pixels = 3.0

    def detect_reference_object(
        self,
        image_bytes: bytes | None = None,
        reference_mode: str = "none",
        known_width_mm: float | None = None,
        known_height_mm: float | None = None,
        manual_bbox: dict[str, Any] | Any | None = None,
        manual_polygon: list[dict[str, Any]] | list[Any] | None = None,
        detection_confidence: float | None = None,
        same_plane_confidence: float | None = None,
        distortion_score: float | None = None,
        source: str = "manual",
        foot_mask: np.ndarray | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> ReferenceObjectDetectionResult:
        mode = str(reference_mode or "none")
        if mode == "none":
            return self._needs_reference(
                mode,
                issues=["Reference object mode is not selected."],
                instructions=["Select credit card, A4 paper, calibration card, or custom object."],
            )

        width_mm, height_mm = self._known_dimensions(mode, known_width_mm, known_height_mm)
        if not width_mm or not height_mm:
            return self._needs_reference(
                mode,
                issues=["Known reference object dimensions are required."],
                instructions=["Enter the reference object width and height in millimeters."],
            )

        bbox = self._normalize_bbox(manual_bbox)
        polygon = self._normalize_polygon(manual_polygon)
        inferred_source = source
        calibration_evidence: dict[str, Any] | None = None

        if bbox is None and polygon is None and image_bytes:
            auto = self._auto_detect_rectangle(
                image_bytes=image_bytes,
                mode=mode,
                known_width_mm=width_mm,
                known_height_mm=height_mm,
            )
            if not auto.detected:
                return auto
            bbox = auto.bbox
            polygon = auto.polygon
            detection_confidence = auto.confidence
            distortion_score = auto.distortion_score
            inferred_source = "auto_detected"

        if bbox is None and polygon is not None:
            bbox = self._bbox_from_polygon(polygon)
        if polygon is None and bbox is not None:
            polygon = self.estimate_object_polygon(bbox)
        if bbox is None:
            return self._needs_reference(
                mode,
                issues=["Reference object bbox or polygon is required."],
                instructions=["Keep the reference object fully visible beside your foot."],
            )

        if mode == "calibration_card" and image_bytes and polygon is not None:
            try:
                rgb = np.array(Image.open(BytesIO(image_bytes)).convert("RGB"))
                calibration_evidence = CalibrationCardService().inspect(rgb, polygon).to_dict()
            except Exception:
                calibration_evidence = {"marker_confidence": 0.0, "issues": ["Calibration card could not be inspected."]}

        confidence = self._clamp(
            detection_confidence if detection_confidence is not None else (0.95 if source != "auto_detected" else 0.0)
        )
        distortion = self._clamp(
            distortion_score
            if distortion_score is not None
            else self.calculate_distortion_score(polygon)
        )
        same_plane = self._clamp(
            same_plane_confidence
            if same_plane_confidence is not None
            else 0.9 - self.calculate_same_plane_risk(bbox, foot_mask)
        )

        issues: list[str] = []
        instructions: list[str] = []
        if confidence < self.minimum_detection_confidence:
            issues.append("Reference object detection confidence is too low.")
            instructions.append("Retake with the full reference object clearly visible.")
        if distortion > self.maximum_distortion_score:
            issues.append("Reference object is too distorted for trusted scale.")
            instructions.append("Place the reference object flat and avoid perspective tilt.")
        if same_plane < self.minimum_same_plane_confidence:
            issues.append("Reference object may not be on the same floor plane as the foot.")
            instructions.append("Place the object flat on the floor beside the foot.")
        if self._bbox_is_cropped(bbox, image_size):
            issues.append("Reference object appears cropped at the image edge.")
            instructions.append("Keep the whole reference object inside the frame.")
        if self._overlaps_foot(bbox, foot_mask):
            issues.append("Reference object overlaps the foot mask.")
            instructions.append("Place the reference object beside the foot, not under it.")
        if calibration_evidence and calibration_evidence["marker_confidence"] < CalibrationCardService.minimum_marker_confidence:
            issues.extend(calibration_evidence.get("issues", []))
            instructions.append("Keep all four calibration card markers visible and flat.")

        detected = len(issues) == 0
        reference_object = (
            self.create_scale_input(
                reference_mode=mode,
                known_width_mm=width_mm,
                known_height_mm=height_mm,
                bbox=bbox,
                polygon=polygon,
                detection_confidence=confidence,
                same_plane_confidence=same_plane,
                distortion_score=distortion,
                source=inferred_source,
                calibration_evidence=calibration_evidence,
            )
            if detected
            else None
        )
        return ReferenceObjectDetectionResult(
            detected=detected,
            reference_mode=mode,
            bbox=bbox,
            polygon=polygon,
            confidence=round(confidence, 4),
            distortion_score=round(distortion, 4),
            same_plane_confidence=round(same_plane, 4),
            source=inferred_source,
            reference_object=reference_object,
            issues=issues,
            instructions=instructions,
        )

    def validate_reference_object(self, **kwargs: Any) -> ReferenceObjectDetectionResult:
        return self.detect_reference_object(**kwargs)

    def estimate_object_polygon(self, bbox: dict[str, float]) -> list[dict[str, float]]:
        x = float(bbox["x"])
        y = float(bbox["y"])
        width = float(bbox["width"])
        height = float(bbox["height"])
        return [
            {"x": x, "y": y},
            {"x": x + width, "y": y},
            {"x": x + width, "y": y + height},
            {"x": x, "y": y + height},
        ]

    def calculate_distortion_score(self, polygon: list[dict[str, float]] | None) -> float:
        if not polygon or len(polygon) != 4:
            return 0.0
        points = np.array([[point["x"], point["y"]] for point in polygon], dtype=np.float32)
        side_lengths = [
            float(np.linalg.norm(points[(idx + 1) % 4] - points[idx]))
            for idx in range(4)
        ]
        if min(side_lengths) <= 0:
            return 1.0
        horizontal_consistency = min(side_lengths[0], side_lengths[2]) / max(
            side_lengths[0],
            side_lengths[2],
        )
        vertical_consistency = min(side_lengths[1], side_lengths[3]) / max(
            side_lengths[1],
            side_lengths[3],
        )
        return 1.0 - min(horizontal_consistency, vertical_consistency)

    def calculate_same_plane_risk(
        self,
        bbox: dict[str, float] | None,
        foot_mask: np.ndarray | None = None,
    ) -> float:
        if bbox is None:
            return 1.0
        if foot_mask is None:
            return 0.0
        foot_box = self._foot_bbox(foot_mask)
        if foot_box is None:
            return 0.25
        ref_center_y = float(bbox["y"]) + float(bbox["height"]) / 2.0
        foot_center_y = foot_box["y"] + foot_box["height"] / 2.0
        image_height = max(float(foot_mask.shape[0]), 1.0)
        return min(abs(ref_center_y - foot_center_y) / image_height, 1.0)

    def create_scale_input(
        self,
        reference_mode: str,
        known_width_mm: float,
        known_height_mm: float,
        bbox: dict[str, float],
        polygon: list[dict[str, float]] | None,
        detection_confidence: float,
        same_plane_confidence: float,
        distortion_score: float,
        source: str,
        calibration_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": reference_mode,
            "reference_mode": reference_mode,
            "known_width_mm": known_width_mm,
            "known_height_mm": known_height_mm,
            "bbox": bbox,
            "polygon": polygon,
            "detection_confidence": detection_confidence,
            "same_plane_confidence": same_plane_confidence,
            "distortion_score": distortion_score,
            "source": source,
            "calibration_evidence": calibration_evidence,
        }

    def _auto_detect_rectangle(
        self,
        image_bytes: bytes,
        mode: str,
        known_width_mm: float,
        known_height_mm: float,
    ) -> ReferenceObjectDetectionResult:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return self._needs_reference(
                mode,
                issues=["Image could not be read for reference object detection."],
                instructions=["Retake or upload a readable image."],
            )
        rgb = np.array(image)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_area = float(rgb.shape[0] * rgb.shape[1])
        expected_ratio = max(known_width_mm, known_height_mm) / min(known_width_mm, known_height_mm)
        candidates: list[tuple[float, dict[str, float], list[dict[str, float]], float]] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < image_area * 0.005:
                continue
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
            if len(approx) != 4:
                continue
            x, y, width, height = cv2.boundingRect(approx)
            if width <= 0 or height <= 0:
                continue
            ratio = max(width, height) / min(width, height)
            ratio_error = abs(ratio - expected_ratio) / expected_ratio
            if ratio_error > 0.22:
                continue
            polygon = [{"x": float(point[0][0]), "y": float(point[0][1])} for point in approx]
            bbox = {"x": float(x), "y": float(y), "width": float(width), "height": float(height)}
            distortion = self.calculate_distortion_score(polygon)
            score = max(0.0, 0.9 - ratio_error - distortion * 0.5)
            candidates.append((score, bbox, polygon, distortion))

        if not candidates:
            return self._needs_reference(
                mode,
                issues=["Reference object was not confidently detected."],
                instructions=["Place the reference object fully visible beside your foot and retake."],
            )
        candidates.sort(key=lambda item: item[0], reverse=True)
        if len(candidates) > 1 and candidates[1][0] >= candidates[0][0] - 0.05:
            return self._needs_reference(
                mode,
                issues=["Multiple possible reference objects were detected."],
                instructions=["Use one clear reference object or adjust it manually."],
            )
        confidence, bbox, polygon, distortion = candidates[0]
        return self.detect_reference_object(
            reference_mode=mode,
            known_width_mm=known_width_mm,
            known_height_mm=known_height_mm,
            manual_bbox=bbox,
            manual_polygon=polygon,
            detection_confidence=confidence,
            same_plane_confidence=0.85,
            distortion_score=distortion,
            source="auto_detected",
            image_size=(rgb.shape[1], rgb.shape[0]),
        )

    def _known_dimensions(
        self,
        mode: str,
        known_width_mm: float | None,
        known_height_mm: float | None,
    ) -> tuple[float | None, float | None]:
        defaults = self.known_dimensions_mm.get(mode)
        if defaults:
            return known_width_mm or defaults[0], known_height_mm or defaults[1]
        return known_width_mm, known_height_mm

    def _normalize_bbox(self, value: dict[str, Any] | Any | None) -> dict[str, float] | None:
        payload = self._as_payload(value)
        if not payload:
            return None
        try:
            x = float(payload["x"])
            y = float(payload["y"])
            width = float(payload["width"])
            height = float(payload["height"])
        except (KeyError, TypeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            return None
        return {"x": x, "y": y, "width": width, "height": height}

    def _normalize_polygon(self, value: list[dict[str, Any]] | list[Any] | None) -> list[dict[str, float]] | None:
        if not value:
            return None
        points: list[dict[str, float]] = []
        for item in value:
            payload = self._as_payload(item)
            try:
                points.append({"x": float(payload["x"]), "y": float(payload["y"])})
            except (KeyError, TypeError, ValueError):
                return None
        return points if len(points) >= 4 else None

    def _bbox_from_polygon(self, polygon: list[dict[str, float]]) -> dict[str, float]:
        xs = [point["x"] for point in polygon]
        ys = [point["y"] for point in polygon]
        return {
            "x": min(xs),
            "y": min(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

    def _bbox_is_cropped(
        self,
        bbox: dict[str, float],
        image_size: tuple[int, int] | None,
    ) -> bool:
        if image_size is None:
            return False
        image_width, image_height = image_size
        return (
            bbox["x"] <= self.edge_margin_pixels
            or bbox["y"] <= self.edge_margin_pixels
            or bbox["x"] + bbox["width"] >= image_width - self.edge_margin_pixels
            or bbox["y"] + bbox["height"] >= image_height - self.edge_margin_pixels
        )

    def _overlaps_foot(self, bbox: dict[str, float], foot_mask: np.ndarray | None) -> bool:
        if foot_mask is None:
            return False
        x0 = max(int(bbox["x"]), 0)
        y0 = max(int(bbox["y"]), 0)
        x1 = min(int(bbox["x"] + bbox["width"]), foot_mask.shape[1])
        y1 = min(int(bbox["y"] + bbox["height"]), foot_mask.shape[0])
        if x1 <= x0 or y1 <= y0:
            return False
        region = foot_mask[y0:y1, x0:x1]
        return bool(np.count_nonzero(region) / max(region.size, 1) > 0.05)

    def _foot_bbox(self, foot_mask: np.ndarray) -> dict[str, float] | None:
        ys, xs = np.where(foot_mask > 0)
        if len(xs) == 0:
            return None
        return {
            "x": float(xs.min()),
            "y": float(ys.min()),
            "width": float(xs.max() - xs.min() + 1),
            "height": float(ys.max() - ys.min() + 1),
        }

    def _needs_reference(
        self,
        mode: str,
        issues: list[str],
        instructions: list[str],
    ) -> ReferenceObjectDetectionResult:
        return ReferenceObjectDetectionResult(
            detected=False,
            reference_mode=mode,
            confidence=0.0,
            distortion_score=1.0,
            same_plane_confidence=0.0,
            issues=issues,
            instructions=instructions,
        )

    def _as_payload(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        return {}

    def _clamp(self, value: float | None) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        return max(0.0, min(parsed, 1.0))

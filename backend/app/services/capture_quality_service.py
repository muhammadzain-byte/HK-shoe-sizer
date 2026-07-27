from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from typing import Any

from PIL import Image, ImageStat

from app.services.ai.contracts import (
    BoundingBox,
    FootSegmentationService,
    SegmentationResult,
)


@dataclass(frozen=True)
class CaptureQualityAnalysis:
    capture_status: str
    score: float
    issues: list[str]
    instructions: list[str]
    frame_quality: dict[str, float]
    foot_visibility: dict[str, Any]
    pose_quality: dict[str, float]
    distance_quality: dict[str, Any]
    guidance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.capture_status == "ready",
            "stage": "capture_quality",
            "status": self.capture_status,
            "capture_status": self.capture_status,
            "score": self.score,
            "issues": self.issues,
            "instructions": self.instructions,
            "frame_quality": self.frame_quality,
            "foot_visibility": self.foot_visibility,
            "pose_quality": self.pose_quality,
            "distance_quality": self.distance_quality,
            "guidance": self.guidance,
        }


class CaptureQualityService:
    """Guided-capture quality gate for pre-measurement foot images."""

    def __init__(
        self,
        foot_segmentation_service: FootSegmentationService | None = None,
        *,
        enable_segmentation: bool = True,
    ) -> None:
        self.foot_segmentation_service = foot_segmentation_service
        self.enable_segmentation = enable_segmentation

    def analyze_bytes(
        self,
        image_bytes: bytes,
        device_metadata: dict[str, Any] | None = None,
    ) -> CaptureQualityAnalysis:
        try:
            image = Image.open(BytesIO(image_bytes))
            image.verify()
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return self._unreadable_result()
        return self.analyze_image(image, device_metadata=device_metadata)

    def analyze_image(
        self,
        image: Image.Image,
        device_metadata: dict[str, Any] | None = None,
    ) -> CaptureQualityAnalysis:
        frame_quality = self._frame_quality(image)
        issues: list[str] = []
        instructions: list[str] = []

        if frame_quality["blur_score"] < 0.35:
            issues.append("image_blurry")
            instructions.append("Hold still and retake the photo.")
        if frame_quality["lighting_score"] < 0.35:
            issues.append("low_light")
            instructions.append("Improve lighting.")
        if frame_quality["overexposure_score"] < 0.35:
            issues.append("overexposed")
            instructions.append("Reduce glare or move away from harsh light.")

        if (
            frame_quality["blur_score"] < 0.18
            or frame_quality["lighting_score"] < 0.18
            or frame_quality["overexposure_score"] < 0.18
        ):
            return self._frame_reject_result(frame_quality, issues, instructions)

        segmentation: SegmentationResult | None = None
        try:
            segmentation = self._segment(image) if self.enable_segmentation else self._fast_segment(image)
        except Exception:
            issues.append("segmentation_failed")
            instructions.append("Place one bare foot clearly inside the guide.")

        visibility = self._foot_visibility(image, segmentation)
        pose = self._pose_quality(image, segmentation, device_metadata or {})
        distance = self._distance_quality(image, segmentation)

        self._visibility_guidance(visibility, issues, instructions)
        self._pose_guidance(pose, issues, instructions)
        self._distance_guidance(distance, issues, instructions)

        score = self._score(frame_quality, visibility, pose, distance)
        critical_reject = (
            "segmentation_failed" in issues
            or frame_quality["blur_score"] < 0.18
            or frame_quality["lighting_score"] < 0.18
            or frame_quality["overexposure_score"] < 0.18
            or not visibility["foot_detected"]
            or not visibility["one_foot_only"]
        )
        if critical_reject:
            status = "reject"
        elif score >= 0.82 and not issues:
            status = "ready"
        else:
            status = "needs_adjustment"

        if status == "ready":
            primary = "Ready to capture."
        elif instructions:
            primary = instructions[0]
        else:
            primary = "Adjust foot inside the guide."
            instructions.append(primary)

        return CaptureQualityAnalysis(
            capture_status=status,
            score=round(score, 4),
            issues=issues,
            instructions=self._dedupe(instructions),
            frame_quality={key: round(value, 4) for key, value in frame_quality.items()},
            foot_visibility=visibility,
            pose_quality={key: round(value, 4) for key, value in pose.items()},
            distance_quality=distance,
            guidance={
                "primary_instruction": primary,
                "secondary_instructions": self._dedupe(instructions[1:]),
            },
        )

    def _frame_quality(self, image: Image.Image) -> dict[str, float]:
        import cv2
        import numpy as np

        grayscale = image.convert("L")
        stat = ImageStat.Stat(grayscale)
        mean_luminance = stat.mean[0]
        histogram = grayscale.histogram()
        total_pixels = max(sum(histogram), 1)
        dark_ratio = sum(histogram[:35]) / total_pixels
        bright_ratio = sum(histogram[245:]) / total_pixels
        laplacian_variance = float(cv2.Laplacian(np.asarray(grayscale), cv2.CV_64F).var())
        blur_score = min(laplacian_variance / 180.0, 1.0)
        lighting_score = max(0.0, min(1.0, 1.0 - abs(mean_luminance - 140.0) / 110.0))
        lighting_score = min(lighting_score, 1.0 - min(dark_ratio / 0.55, 1.0) * 0.65)
        overexposure_score = max(0.0, 1.0 - min(bright_ratio / 0.35, 1.0))
        if mean_luminance > 225:
            overexposure_score = min(overexposure_score, 0.25)
        return {
            "blur_score": blur_score,
            "lighting_score": lighting_score,
            "overexposure_score": overexposure_score,
        }

    def _foot_visibility(
        self,
        image: Image.Image,
        segmentation: SegmentationResult | None,
    ) -> dict[str, Any]:
        width, height = image.size
        bbox = segmentation.foot_bbox if segmentation and segmentation.foot_bbox else None
        if bbox is None:
            return {
                "foot_detected": False,
                "one_foot_only": False,
                "toes_visible": False,
                "heel_visible": False,
                "full_foot_visible": False,
                "lower_leg_ratio": 1.0,
                "toe_margin_ratio": 0.0,
                "heel_margin_ratio": 0.0,
                "side_margin_ratio": 0.0,
            }

        toe_margin = bbox.y / max(height, 1)
        heel_margin = (height - (bbox.y + bbox.height)) / max(height, 1)
        side_margin = min(bbox.x, width - (bbox.x + bbox.width)) / max(width, 1)
        lower_leg_ratio = self._lower_leg_ratio(segmentation, bbox)
        toes_visible = toe_margin >= 0.025
        heel_visible = heel_margin >= 0.025
        side_visible = side_margin >= 0.025
        return {
            "foot_detected": bool(segmentation and segmentation.foot_count > 0),
            "one_foot_only": bool(segmentation and segmentation.foot_count == 1),
            "toes_visible": toes_visible,
            "heel_visible": heel_visible,
            "full_foot_visible": toes_visible and heel_visible and side_visible,
            "lower_leg_ratio": round(lower_leg_ratio, 4),
            "toe_margin_ratio": round(toe_margin, 4),
            "heel_margin_ratio": round(heel_margin, 4),
            "side_margin_ratio": round(side_margin, 4),
        }

    def _pose_quality(
        self,
        image: Image.Image,
        segmentation: SegmentationResult | None,
        device_metadata: dict[str, Any],
    ) -> dict[str, float]:
        bbox = segmentation.foot_bbox if segmentation and segmentation.foot_bbox else None
        aspect_ratio = bbox.height / max(bbox.width, 1) if bbox else 0.0
        aspect_score = 1.0 - min(abs(aspect_ratio - 2.35) / 1.5, 1.0) if bbox else 0.0
        orientation = device_metadata.get("orientation") or {}
        beta = self._float_or_none(orientation.get("beta"))
        gamma = self._float_or_none(orientation.get("gamma"))
        tilt = max(abs(beta or 0.0), abs(gamma or 0.0))
        tilt_risk = min(max((tilt - 12.0) / 32.0, 0.0), 1.0) if (beta is not None or gamma is not None) else 0.35
        perspective_risk = max(0.0, min(1.0, (1.0 - aspect_score) * 0.75 + tilt_risk * 0.25))
        return {
            "top_down_score": max(0.0, min(1.0, 1.0 - perspective_risk)),
            "rotation_angle_degrees": 0.0,
            "perspective_risk": perspective_risk,
            "foot_flatness_risk": tilt_risk,
        }

    def _distance_quality(
        self,
        image: Image.Image,
        segmentation: SegmentationResult | None,
    ) -> dict[str, Any]:
        bbox = segmentation.foot_bbox if segmentation and segmentation.foot_bbox else None
        if bbox is None:
            return {
                "foot_frame_coverage": 0.0,
                "too_close": False,
                "too_far": True,
                "distance_confidence": 0.0,
            }
        image_area = max(image.width * image.height, 1)
        coverage = (bbox.width * bbox.height) / image_area
        height_ratio = bbox.height / max(image.height, 1)
        too_close = height_ratio > 0.82 or coverage > 0.48
        too_far = height_ratio < 0.38 or coverage < 0.10
        confidence = 1.0 - min(abs(height_ratio - 0.66) / 0.44, 1.0)
        return {
            "foot_frame_coverage": round(coverage, 4),
            "too_close": too_close,
            "too_far": too_far,
            "distance_confidence": round(confidence, 4),
        }

    def _visibility_guidance(self, visibility: dict[str, Any], issues: list[str], instructions: list[str]) -> None:
        if not visibility["foot_detected"]:
            issues.append("no_foot_detected")
            instructions.append("Place one bare foot inside the guide.")
        if visibility["foot_detected"] and not visibility["one_foot_only"]:
            issues.append("multiple_feet_detected")
            instructions.append("Keep one bare foot only.")
        if not visibility["toes_visible"]:
            issues.append("toes_near_frame_edge")
            instructions.append("Keep all toes inside the frame.")
        if not visibility["heel_visible"]:
            issues.append("heel_near_frame_edge")
            instructions.append("Show the full heel.")
        if visibility["side_margin_ratio"] < 0.025:
            issues.append("foot_not_centered")
            instructions.append("Center your foot inside the guide.")
        if visibility["lower_leg_ratio"] > 0.22:
            issues.append("lower_leg_too_visible")
            instructions.append("Move your leg back; too much lower leg is visible.")

    def _pose_guidance(self, pose: dict[str, float], issues: list[str], instructions: list[str]) -> None:
        if pose["perspective_risk"] > 0.55:
            issues.append("camera_not_top_down")
            instructions.append("Hold phone directly above the foot.")
        if pose["foot_flatness_risk"] > 0.55:
            issues.append("phone_tilted")
            instructions.append("Hold phone parallel to the floor.")

    def _distance_guidance(self, distance: dict[str, Any], issues: list[str], instructions: list[str]) -> None:
        if distance["too_close"]:
            issues.append("camera_too_close")
            instructions.append("Move phone slightly higher.")
        if distance["too_far"]:
            issues.append("camera_too_far")
            instructions.append("Move phone closer.")

    def _score(
        self,
        frame_quality: dict[str, float],
        visibility: dict[str, Any],
        pose: dict[str, float],
        distance: dict[str, Any],
    ) -> float:
        visibility_score = (
            0.20 * float(visibility["foot_detected"])
            + 0.18 * float(visibility["one_foot_only"])
            + 0.17 * float(visibility["toes_visible"])
            + 0.17 * float(visibility["heel_visible"])
            + 0.14 * float(visibility["full_foot_visible"])
            + 0.14 * max(0.0, 1.0 - min(visibility["lower_leg_ratio"] / 0.28, 1.0))
        )
        frame_score = (
            0.38 * frame_quality["blur_score"]
            + 0.34 * frame_quality["lighting_score"]
            + 0.28 * frame_quality["overexposure_score"]
        )
        distance_score = distance["distance_confidence"]
        if distance["too_close"] or distance["too_far"]:
            distance_score *= 0.45
        return (
            0.34 * visibility_score
            + 0.26 * frame_score
            + 0.22 * pose["top_down_score"]
            + 0.18 * distance_score
        )

    def _lower_leg_ratio(self, segmentation: SegmentationResult | None, bbox: BoundingBox) -> float:
        selected = segmentation.feet[0] if segmentation and segmentation.feet else None
        diagnostics = selected.diagnostics if selected and selected.diagnostics else {}
        refinement = diagnostics.get("refinement") if isinstance(diagnostics, dict) else None
        if isinstance(refinement, dict):
            ratio = self._float_or_none(refinement.get("removed_lower_leg_area_ratio"))
            if ratio is not None:
                return max(0.0, min(ratio, 1.0))
        aspect_ratio = bbox.height / max(bbox.width, 1)
        return max(0.0, min((aspect_ratio - 2.7) / 2.0, 0.45))

    def _segment(self, image: Image.Image) -> SegmentationResult:
        if self.foot_segmentation_service is None:
            from app.services.ai.sam2_foot_segmentation_service import SAM2FootSegmentationService

            self.foot_segmentation_service = SAM2FootSegmentationService()
        return self.foot_segmentation_service.segment(image)

    def _fast_segment(self, image: Image.Image) -> SegmentationResult | None:
        """Estimate a foreground foot region without loading the measurement model.

        Capture guidance must return promptly on a phone. Full SAM 2 inference is
        deliberately deferred to the explicit analysis pipeline after upload.
        """
        import cv2
        import numpy as np

        rgb = np.asarray(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = np.ones((7, 7), dtype=np.uint8)
        threshold = cv2.morphologyEx(threshold, cv2.MORPH_OPEN, kernel)
        threshold = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        image_area = max(image.width * image.height, 1)
        candidates = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            x, y, width, height = cv2.boundingRect(contour)
            area_ratio = area / image_area
            if area_ratio < 0.025 or area_ratio > 0.82 or width < 20 or height < 20:
                continue
            candidates.append((area, BoundingBox(x=x, y=y, width=width, height=height)))

        if not candidates:
            return None
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        _, bbox = candidates[0]
        return SegmentationResult(
            mask_uri=None,
            confidence_score=Decimal("0.55"),
            model_name="fast_capture_quality",
            foot_count=min(len(candidates), 2),
            foot_bbox=bbox,
            edge_contact_detected=self._bbox_touches_edge(bbox, image.size),
            feet=None,
        )

    def _bbox_touches_edge(self, bbox: BoundingBox, image_size: tuple[int, int]) -> bool:
        width, height = image_size
        margin_x = max(int(width * 0.025), 1)
        margin_y = max(int(height * 0.025), 1)
        return (
            bbox.x <= margin_x
            or bbox.y <= margin_y
            or bbox.x + bbox.width >= width - margin_x
            or bbox.y + bbox.height >= height - margin_y
        )

    def _unreadable_result(self) -> CaptureQualityAnalysis:
        return CaptureQualityAnalysis(
            capture_status="reject",
            score=0.0,
            issues=["image_unreadable"],
            instructions=["Retake the photo."],
            frame_quality={"blur_score": 0.0, "lighting_score": 0.0, "overexposure_score": 0.0},
            foot_visibility={
                "foot_detected": False,
                "one_foot_only": False,
                "toes_visible": False,
                "heel_visible": False,
                "full_foot_visible": False,
                "lower_leg_ratio": 1.0,
                "toe_margin_ratio": 0.0,
                "heel_margin_ratio": 0.0,
                "side_margin_ratio": 0.0,
            },
            pose_quality={
                "top_down_score": 0.0,
                "rotation_angle_degrees": 0.0,
                "perspective_risk": 1.0,
                "foot_flatness_risk": 1.0,
            },
            distance_quality={
                "foot_frame_coverage": 0.0,
                "too_close": False,
                "too_far": True,
                "distance_confidence": 0.0,
            },
            guidance={
                "primary_instruction": "Retake the photo.",
                "secondary_instructions": [],
            },
        )

    def _frame_reject_result(
        self,
        frame_quality: dict[str, float],
        issues: list[str],
        instructions: list[str],
    ) -> CaptureQualityAnalysis:
        primary = instructions[0] if instructions else "Retake the photo with a clearer view."
        return CaptureQualityAnalysis(
            capture_status="reject",
            score=round(
                0.38 * frame_quality["blur_score"]
                + 0.34 * frame_quality["lighting_score"]
                + 0.28 * frame_quality["overexposure_score"],
                4,
            ),
            issues=self._dedupe(issues or ["frame_quality_failed"]),
            instructions=self._dedupe(instructions or [primary]),
            frame_quality={key: round(value, 4) for key, value in frame_quality.items()},
            foot_visibility={
                "foot_detected": False,
                "one_foot_only": False,
                "toes_visible": False,
                "heel_visible": False,
                "full_foot_visible": False,
                "lower_leg_ratio": 1.0,
                "toe_margin_ratio": 0.0,
                "heel_margin_ratio": 0.0,
                "side_margin_ratio": 0.0,
            },
            pose_quality={
                "top_down_score": 0.0,
                "rotation_angle_degrees": 0.0,
                "perspective_risk": 1.0,
                "foot_flatness_risk": 1.0,
            },
            distance_quality={
                "foot_frame_coverage": 0.0,
                "too_close": False,
                "too_far": True,
                "distance_confidence": 0.0,
            },
            guidance={
                "primary_instruction": primary,
                "secondary_instructions": self._dedupe(instructions[1:]),
            },
        )

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped

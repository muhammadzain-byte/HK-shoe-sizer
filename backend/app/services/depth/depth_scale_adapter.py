from __future__ import annotations

from typing import Any

from app.services.depth.contracts import DepthScaleEvidence
from app.services.depth.depth_validation_service import DepthValidationService


class DepthScaleAdapter:
    """Converts strong depth metadata into scale using a conservative pinhole approximation."""

    minimum_confidence = 0.85

    def __init__(self, validation_service: DepthValidationService | None = None) -> None:
        self.validation_service = validation_service or DepthValidationService()

    def estimate_scale(
        self,
        measurement: dict[str, Any],
        depth_metadata: dict[str, Any] | Any,
        image_metadata: dict[str, Any] | None = None,
        capture_session: dict[str, Any] | Any | None = None,
    ) -> dict[str, Any]:
        capture_payload = self._as_payload(capture_session)
        capture_status = capture_payload.get("capture_status")
        if capture_status == "reject":
            return self._blocked(
                "unavailable",
                ["Capture quality was rejected, so depth scale is blocked."],
                ["Retake the capture before estimating real-world scale."],
            )
        if capture_status and capture_status != "ready":
            return self._blocked(
                "low_confidence",
                ["Capture quality is not ready for depth scale."],
                ["Retake until capture quality is ready."],
            )
        if measurement.get("measurement_status") != "trusted":
            return self._blocked(
                "unavailable",
                ["Measurement must be trusted before depth scale can be estimated."],
                ["Complete landmark validation before depth scale conversion."],
            )

        metadata = self.validation_service.normalize(depth_metadata)
        quality = self.validation_service.validate(metadata)
        if quality.depth_status != "available" or not quality.can_support_scale:
            return {
                "scale_status": quality.depth_status,
                "scale_mode": "ar_depth" if metadata.depth_mode != "monocular" else "monocular_depth_model",
                "pixels_per_mm": None,
                "mm_per_pixel": None,
                "confidence": quality.confidence,
                "evidence": {"depth_quality": quality.to_dict()},
                "issues": quality.issues,
                "instructions": quality.instructions,
            }

        intrinsics = metadata.camera_intrinsics
        distance_mm = metadata.distance_to_foot_plane_mm
        if not intrinsics or not intrinsics.fx or not intrinsics.fy or not distance_mm:
            return self._blocked(
                "low_confidence",
                ["Depth metadata is missing intrinsics or distance to foot plane."],
                ["Provide fx, fy, and distance to foot plane."],
            )

        image_payload = image_metadata or {}
        image_width = self._int_or_none(image_payload.get("width") or image_payload.get("image_width"))
        image_height = self._int_or_none(image_payload.get("height") or image_payload.get("image_height"))
        if image_width and intrinsics.width and image_width != intrinsics.width:
            return self._blocked(
                "low_confidence",
                ["Image width does not match depth camera intrinsics."],
                ["Use depth metadata from the same captured frame."],
            )
        if image_height and intrinsics.height and image_height != intrinsics.height:
            return self._blocked(
                "low_confidence",
                ["Image height does not match depth camera intrinsics."],
                ["Use depth metadata from the same captured frame."],
            )

        mm_per_pixel_x = distance_mm / intrinsics.fx
        mm_per_pixel_y = distance_mm / intrinsics.fy
        consistency = min(mm_per_pixel_x, mm_per_pixel_y) / max(mm_per_pixel_x, mm_per_pixel_y)
        mm_per_pixel = (mm_per_pixel_x + mm_per_pixel_y) / 2.0
        pixels_per_mm = 1.0 / mm_per_pixel
        confidence = min(quality.confidence * consistency, 0.95)
        evidence = DepthScaleEvidence(
            can_estimate_scale=confidence >= self.minimum_confidence,
            pixels_per_mm=round(pixels_per_mm, 6),
            mm_per_pixel=round(mm_per_pixel, 6),
            confidence=round(confidence, 4),
            evidence={
                "depth_mode": metadata.depth_mode,
                "distance_to_foot_plane_mm": distance_mm,
                "fx": intrinsics.fx,
                "fy": intrinsics.fy,
                "image_width": intrinsics.width,
                "image_height": intrinsics.height,
                "pinhole_mm_per_pixel_x": round(mm_per_pixel_x, 6),
                "pinhole_mm_per_pixel_y": round(mm_per_pixel_y, 6),
                "scale_consistency": round(consistency, 4),
            },
            issues=[],
        )
        if not evidence.can_estimate_scale:
            return {
                "scale_status": "low_confidence",
                "scale_mode": "ar_depth",
                "pixels_per_mm": None,
                "mm_per_pixel": None,
                "confidence": evidence.confidence,
                "evidence": evidence.to_dict(),
                "issues": ["Depth scale confidence is below trusted threshold."],
                "instructions": ["Use a reference object or stronger depth capture."],
            }
        return {
            "scale_status": "available",
            "scale_mode": "ar_depth",
            "pixels_per_mm": evidence.pixels_per_mm,
            "mm_per_pixel": evidence.mm_per_pixel,
            "confidence": evidence.confidence,
            "evidence": evidence.to_dict(),
            "issues": [],
            "instructions": [],
        }

    def _blocked(
        self,
        status: str,
        issues: list[str],
        instructions: list[str],
    ) -> dict[str, Any]:
        return {
            "scale_status": status,
            "scale_mode": "ar_depth",
            "pixels_per_mm": None,
            "mm_per_pixel": None,
            "confidence": 0.0,
            "evidence": {},
            "issues": issues,
            "instructions": instructions,
        }

    def _as_payload(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "__dict__"):
            return {key: item for key, item in vars(value).items() if not key.startswith("_")}
        return {}

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

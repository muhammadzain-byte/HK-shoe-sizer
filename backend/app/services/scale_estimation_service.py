from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.depth.depth_scale_adapter import DepthScaleAdapter


@dataclass(frozen=True)
class RealWorldMeasurement:
    foot_length_mm: float | None
    foot_width_mm: float | None
    scale_status: str
    measurement_status: str
    can_recommend_size: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "foot_length_mm": self.foot_length_mm,
            "foot_width_mm": self.foot_width_mm,
            "scale_status": self.scale_status,
            "measurement_status": self.measurement_status,
            "can_recommend_size": self.can_recommend_size,
        }


@dataclass(frozen=True)
class ScaleEstimateResult:
    scale_status: str
    scale_mode: str
    pixels_per_mm: float | None
    mm_per_pixel: float | None
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    real_world_measurement: RealWorldMeasurement | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale_status": self.scale_status,
            "scale_mode": self.scale_mode,
            "pixels_per_mm": self.pixels_per_mm,
            "mm_per_pixel": self.mm_per_pixel,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "issues": self.issues,
            "instructions": self.instructions,
            "real_world_measurement": (
                self.real_world_measurement.to_dict() if self.real_world_measurement else None
            ),
        }


class ScaleEstimationService:
    """Safe scale estimator that refuses real-world output without trusted evidence."""

    reference_dimensions_mm = {
        "credit_card": {"width": 85.60, "height": 53.98},
        "a4_paper": {"width": 210.0, "height": 297.0},
    }
    minimum_measurement_status = "trusted"
    minimum_scale_confidence = 0.85
    minimum_reference_confidence = 0.85
    minimum_scale_consistency = 0.85
    maximum_reference_distortion = 0.25
    minimum_same_plane_confidence = 0.75

    def estimate_scale(
        self,
        measurement: dict[str, Any] | Any,
        capture_session: dict[str, Any] | Any | None = None,
        device_metadata: dict[str, Any] | None = None,
        image_metadata: dict[str, Any] | None = None,
        reference_object: dict[str, Any] | Any | None = None,
        calibration_mat: dict[str, Any] | Any | None = None,
        depth_metadata: dict[str, Any] | Any | None = None,
    ) -> ScaleEstimateResult:
        measurement_payload = self._as_payload(measurement)
        status = str(measurement_payload.get("measurement_status") or "unknown")
        if status != self.minimum_measurement_status:
            result = self._unavailable(
                issues=["Measurement must be trusted before scale can be estimated."],
                instructions=["Complete landmark validation before estimating real-world scale."],
            )
            return self._with_real_world(result, measurement_payload)
        capture_payload = self._as_payload(capture_session)
        if capture_payload.get("capture_status") == "reject":
            result = self._unavailable(
                issues=["Capture quality was rejected, so scale estimation is blocked."],
                instructions=["Retake the capture before estimating real-world scale."],
            )
            return self._with_real_world(result, measurement_payload)

        if reference_object is not None:
            return self._with_real_world(
                self.estimate_from_reference_object(reference_object),
                measurement_payload,
            )
        if calibration_mat is not None:
            return self._with_real_world(
                self.estimate_from_calibration_mat(calibration_mat),
                measurement_payload,
            )
        if depth_metadata is None:
            depth_metadata = self._depth_evidence_from_capture(capture_payload)
        if depth_metadata is not None:
            return self._with_real_world(
                self.estimate_from_depth_metadata(
                    depth_metadata,
                    measurement=measurement_payload,
                    capture_session=capture_session,
                    image_metadata=image_metadata,
                ),
                measurement_payload,
            )
        if device_metadata or capture_session:
            return self._with_real_world(
                self.estimate_from_device_profile(capture_session, device_metadata, image_metadata),
                measurement_payload,
            )
        return self._with_real_world(
            self._unavailable(
                issues=["No trusted scale source was provided."],
                instructions=["Use a reference object or supported depth capture mode for real-world sizing."],
            ),
            measurement_payload,
        )

    def _depth_evidence_from_capture(self, capture_payload: dict[str, Any]) -> dict[str, Any] | None:
        """Return native AR evidence only; browser telemetry is never a scale source."""
        metadata = self._as_payload(capture_payload.get("raw_device_metadata"))
        mode = str(metadata.get("capture_mode") or "browser_guidance").lower()
        evidence = self._as_payload(metadata.get("ar_evidence"))
        if mode not in {"arcore", "arkit", "lidar"} or not evidence:
            return None
        evidence_mode = str(evidence.get("depth_mode") or "").lower()
        if evidence_mode != mode and not (mode == "lidar" and evidence_mode == "arkit"):
            return None
        return evidence

    def estimate_from_reference_object(self, reference_object: dict[str, Any] | Any) -> ScaleEstimateResult:
        payload = self._as_payload(reference_object)
        object_type = str(payload.get("type") or payload.get("reference_mode") or "custom_object")
        if object_type == "none":
            return ScaleEstimateResult(
                scale_status="needs_reference",
                scale_mode="reference_object",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=0.0,
                evidence={"reference_object_type": object_type},
                issues=["Reference object mode is not selected."],
                instructions=["Select and capture a trusted reference object."],
            )
        bbox = self._as_payload(payload.get("bbox"))
        if not bbox and payload.get("polygon"):
            bbox = self._bbox_from_polygon(payload.get("polygon"))
        known_width = self._float_or_none(payload.get("known_width_mm"))
        known_height = self._float_or_none(payload.get("known_height_mm"))
        defaults = self.reference_dimensions_mm.get(object_type)
        if defaults:
            known_width = known_width or defaults["width"]
            known_height = known_height or defaults["height"]

        width_px = self._float_or_none(bbox.get("width"))
        height_px = self._float_or_none(bbox.get("height"))
        detection_confidence = self._float_or_default(payload.get("detection_confidence"), 0.0)
        same_plane_confidence = self._float_or_none(payload.get("same_plane_confidence"))
        distortion_score = self._float_or_none(payload.get("distortion_score"))

        evidence = {
            "reference_object_type": object_type,
            "reference_width_pixels": width_px or 0,
            "reference_height_pixels": height_px or 0,
            "known_width_mm": known_width or 0,
            "known_height_mm": known_height or 0,
            "pixels_per_mm_width": 0.0,
            "pixels_per_mm_height": 0.0,
            "scale_consistency": 0.0,
            "same_plane_confidence": same_plane_confidence,
            "distortion_score": distortion_score,
            "source": payload.get("source"),
        }

        if not known_width or not known_height or not width_px or not height_px:
            return ScaleEstimateResult(
                scale_status="needs_reference",
                scale_mode="reference_object",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=0.0,
                evidence=evidence,
                issues=["Reference object dimensions and bbox are required."],
                instructions=["Capture a known reference object in the same plane as the foot."],
            )

        pixels_per_mm_width = width_px / known_width
        pixels_per_mm_height = height_px / known_height
        scale_consistency = min(pixels_per_mm_width, pixels_per_mm_height) / max(
            pixels_per_mm_width,
            pixels_per_mm_height,
        )
        evidence.update(
            {
                "pixels_per_mm_width": round(pixels_per_mm_width, 6),
                "pixels_per_mm_height": round(pixels_per_mm_height, 6),
                "scale_consistency": round(scale_consistency, 4),
            }
        )

        if detection_confidence < self.minimum_reference_confidence:
            return ScaleEstimateResult(
                scale_status="low_confidence",
                scale_mode="reference_object",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=round(detection_confidence, 4),
                evidence=evidence,
                issues=["Reference object detection confidence is too low."],
                instructions=["Retake with the full reference object clearly visible."],
            )
        if distortion_score is not None and distortion_score > self.maximum_reference_distortion:
            return ScaleEstimateResult(
                scale_status="low_confidence",
                scale_mode="reference_object",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=round(max(0.0, detection_confidence - distortion_score), 4),
                evidence=evidence,
                issues=["Reference object is too distorted for trusted scale."],
                instructions=["Keep the reference object flat and avoid perspective tilt."],
            )
        if (
            same_plane_confidence is not None
            and same_plane_confidence < self.minimum_same_plane_confidence
        ):
            return ScaleEstimateResult(
                scale_status="low_confidence",
                scale_mode="reference_object",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=round(detection_confidence * same_plane_confidence, 4),
                evidence=evidence,
                issues=["Reference object may not be on the same floor plane as the foot."],
                instructions=["Place the reference object flat beside the foot, not in your hand."],
            )

        confidence = detection_confidence * scale_consistency
        if same_plane_confidence is not None:
            confidence *= max(0.0, min(same_plane_confidence, 1.0))
        if scale_consistency < self.minimum_scale_consistency:
            return ScaleEstimateResult(
                scale_status="low_confidence",
                scale_mode="reference_object",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=round(confidence, 4),
                evidence=evidence,
                issues=["Reference object scale is inconsistent across width and height."],
                instructions=["Keep the reference object flat and parallel to the foot plane."],
            )

        pixels_per_mm = (pixels_per_mm_width + pixels_per_mm_height) / 2.0
        mm_per_pixel = 1.0 / pixels_per_mm
        return ScaleEstimateResult(
            scale_status="available",
            scale_mode="reference_object",
            pixels_per_mm=round(pixels_per_mm, 6),
            mm_per_pixel=round(mm_per_pixel, 6),
            confidence=round(min(confidence, 0.99), 4),
            evidence=evidence,
            issues=[],
            instructions=[],
        )

    def estimate_from_calibration_mat(self, calibration_mat: dict[str, Any] | Any) -> ScaleEstimateResult:
        payload = self._as_payload(calibration_mat)
        spacing = self._float_or_none(payload.get("marker_spacing_mm"))
        markers = payload.get("detected_markers") or []
        confidence = self._float_or_default(payload.get("detection_confidence"), 0.0)
        if not spacing or len(markers) < 2:
            return ScaleEstimateResult(
                scale_status="needs_reference",
                scale_mode="calibration_mat",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=0.0,
                evidence={"marker_count": len(markers), "marker_spacing_mm": spacing},
                issues=["Calibration mat markers are insufficient."],
                instructions=["Use a calibration mat with visible markers."],
            )
        if confidence < self.minimum_reference_confidence:
            return ScaleEstimateResult(
                scale_status="low_confidence",
                scale_mode="calibration_mat",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=round(confidence, 4),
                evidence={"marker_count": len(markers), "marker_spacing_mm": spacing},
                issues=["Calibration mat detection confidence is too low."],
                instructions=["Retake with the calibration mat fully visible."],
            )
        first = self._as_payload(markers[0])
        second = self._as_payload(markers[1])
        dx = self._float_or_default(second.get("x"), 0.0) - self._float_or_default(first.get("x"), 0.0)
        dy = self._float_or_default(second.get("y"), 0.0) - self._float_or_default(first.get("y"), 0.0)
        pixel_distance = (dx * dx + dy * dy) ** 0.5
        if pixel_distance <= 0:
            return ScaleEstimateResult(
                scale_status="low_confidence",
                scale_mode="calibration_mat",
                pixels_per_mm=None,
                mm_per_pixel=None,
                confidence=0.0,
                evidence={"marker_count": len(markers), "marker_spacing_mm": spacing},
                issues=["Calibration mat markers do not define a valid distance."],
                instructions=["Retake with separated calibration markers."],
            )
        pixels_per_mm = pixel_distance / spacing
        return ScaleEstimateResult(
            scale_status="available",
            scale_mode="calibration_mat",
            pixels_per_mm=round(pixels_per_mm, 6),
            mm_per_pixel=round(1.0 / pixels_per_mm, 6),
            confidence=round(min(confidence, 0.9), 4),
            evidence={
                "marker_count": len(markers),
                "marker_spacing_mm": spacing,
                "marker_distance_pixels": round(pixel_distance, 4),
            },
            issues=[],
            instructions=[],
        )

    def estimate_from_depth_metadata(
        self,
        depth_metadata: dict[str, Any] | Any,
        measurement: dict[str, Any] | None = None,
        capture_session: dict[str, Any] | Any | None = None,
        image_metadata: dict[str, Any] | None = None,
    ) -> ScaleEstimateResult:
        payload = self._as_payload(depth_metadata)
        mode = str(payload.get("depth_mode") or "none")
        if mode == "monocular" and not bool(payload.get("calibrated")):
            return self.estimate_from_monocular_depth(payload)
        adapter_result = DepthScaleAdapter().estimate_scale(
            measurement=measurement or {"measurement_status": self.minimum_measurement_status},
            depth_metadata=payload,
            image_metadata=image_metadata,
            capture_session=capture_session,
        )
        return ScaleEstimateResult(**adapter_result)

    def estimate_from_device_profile(
        self,
        capture_session: dict[str, Any] | Any | None = None,
        device_metadata: dict[str, Any] | None = None,
        image_metadata: dict[str, Any] | None = None,
    ) -> ScaleEstimateResult:
        capture_payload = self._as_payload(capture_session)
        metadata_payload = device_metadata or {}
        evidence = {
            "device_family": capture_payload.get("device_family")
            or metadata_payload.get("device_family"),
            "browser": capture_payload.get("browser") or metadata_payload.get("browser"),
            "os": capture_payload.get("os") or metadata_payload.get("os"),
            "video_width": capture_payload.get("video_width") or metadata_payload.get("video_width"),
            "video_height": capture_payload.get("video_height") or metadata_payload.get("video_height"),
            "image_metadata": image_metadata or {},
        }
        return ScaleEstimateResult(
            scale_status="unavailable",
            scale_mode="device_camera_model",
            pixels_per_mm=None,
            mm_per_pixel=None,
            confidence=0.0,
            evidence=evidence,
            issues=["Device metadata alone is not a trusted scale source."],
            instructions=["Use a reference object or verified device calibration profile."],
        )

    def estimate_from_monocular_depth(self, _metadata: dict[str, Any] | Any | None = None) -> ScaleEstimateResult:
        return ScaleEstimateResult(
            scale_status="unavailable",
            scale_mode="monocular_depth_model",
            pixels_per_mm=None,
            mm_per_pixel=None,
            confidence=0.0,
            evidence={"calibrated": False},
            issues=["Monocular depth is not calibrated for millimeter conversion."],
            instructions=["Use a reference object or calibrated depth capture mode."],
        )

    def apply_scale_to_measurement(
        self,
        measurement: dict[str, Any] | Any,
        scale: ScaleEstimateResult,
    ) -> RealWorldMeasurement:
        payload = self._as_payload(measurement)
        measurement_status = str(payload.get("measurement_status") or "unknown")
        if (
            scale.scale_status != "available"
            or measurement_status != self.minimum_measurement_status
            or not self.validate_scale_confidence(scale)
            or scale.mm_per_pixel is None
        ):
            return RealWorldMeasurement(
                foot_length_mm=None,
                foot_width_mm=None,
                scale_status=scale.scale_status,
                measurement_status=measurement_status,
                can_recommend_size=False,
            )
        length_px = self._float_or_none(payload.get("foot_length_pixels"))
        width_px = self._float_or_none(payload.get("foot_width_pixels"))
        return RealWorldMeasurement(
            foot_length_mm=round(length_px * scale.mm_per_pixel, 2) if length_px is not None else None,
            foot_width_mm=round(width_px * scale.mm_per_pixel, 2) if width_px is not None else None,
            scale_status=scale.scale_status,
            measurement_status=measurement_status,
            can_recommend_size=False,
        )

    def validate_scale_confidence(self, scale: ScaleEstimateResult) -> bool:
        return scale.confidence >= self.minimum_scale_confidence

    def _with_real_world(
        self,
        result: ScaleEstimateResult,
        measurement_payload: dict[str, Any],
    ) -> ScaleEstimateResult:
        real_world = self.apply_scale_to_measurement(measurement_payload, result)
        return ScaleEstimateResult(
            scale_status=result.scale_status,
            scale_mode=result.scale_mode,
            pixels_per_mm=result.pixels_per_mm,
            mm_per_pixel=result.mm_per_pixel,
            confidence=result.confidence,
            evidence=result.evidence,
            issues=result.issues,
            instructions=result.instructions,
            real_world_measurement=real_world,
        )

    def _unavailable(
        self,
        issues: list[str],
        instructions: list[str],
    ) -> ScaleEstimateResult:
        return ScaleEstimateResult(
            scale_status="unavailable",
            scale_mode="unavailable",
            pixels_per_mm=None,
            mm_per_pixel=None,
            confidence=0.0,
            evidence={},
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
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        return {
            key: getattr(value, key)
            for key in dir(value)
            if not key.startswith("_") and not callable(getattr(value, key))
        }

    def _float_or_default(self, value: Any, default: float) -> float:
        parsed = self._float_or_none(value)
        return parsed if parsed is not None else default

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _bbox_from_polygon(self, polygon: Any) -> dict[str, float]:
        points = []
        if isinstance(polygon, list):
            for point in polygon:
                payload = self._as_payload(point)
                x = self._float_or_none(payload.get("x"))
                y = self._float_or_none(payload.get("y"))
                if x is not None and y is not None:
                    points.append((x, y))
        if not points:
            return {}
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return {
            "x": min(xs),
            "y": min(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

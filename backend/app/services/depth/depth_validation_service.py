from __future__ import annotations

from typing import Any

from app.services.depth.contracts import CameraIntrinsics, DepthMetadata, DepthQualityResult, PlaneEstimate


class DepthValidationService:
    supported_modes = {"arcore", "arkit", "lidar", "monocular", "uploaded_depth"}
    minimum_plane_confidence = 0.80
    minimum_depth_confidence = 0.80
    minimum_distance_to_foot_plane_mm = 250.0
    maximum_distance_to_foot_plane_mm = 2500.0

    def validate(self, depth_metadata: dict[str, Any] | DepthMetadata | None) -> DepthQualityResult:
        metadata = self.normalize(depth_metadata)
        issues: list[str] = []
        instructions: list[str] = []

        if not metadata.depth_available or metadata.depth_mode == "none":
            return DepthQualityResult(
                depth_status="unavailable",
                depth_mode=metadata.depth_mode,
                confidence=0.0,
                issues=["Depth metadata is unavailable."],
                instructions=["Use a supported depth capture mode or reference object."],
                can_support_scale=False,
            )
        if metadata.depth_mode not in self.supported_modes:
            return DepthQualityResult(
                depth_status="unavailable",
                depth_mode=metadata.depth_mode,
                confidence=0.0,
                issues=["Depth mode is unsupported."],
                instructions=["Use ARCore, ARKit, LiDAR, uploaded depth, or a reference object."],
                can_support_scale=False,
            )
        if not self._intrinsics_complete(metadata.camera_intrinsics):
            issues.append("Camera intrinsics are incomplete.")
            instructions.append("Provide fx, fy, cx, cy, width, and height from the capture device.")
        if metadata.plane_confidence < self.minimum_plane_confidence:
            issues.append("Depth plane confidence is too low.")
            instructions.append("Retake with a clearer floor or foot plane.")
        if metadata.depth_confidence < self.minimum_depth_confidence:
            issues.append("Depth confidence is too low.")
            instructions.append("Retake with stronger depth tracking.")
        if metadata.distance_to_foot_plane_mm is None:
            issues.append("Distance to foot plane is missing.")
            instructions.append("Provide distance to the foot plane from the depth capture.")
        elif not self.minimum_distance_to_foot_plane_mm <= metadata.distance_to_foot_plane_mm <= self.maximum_distance_to_foot_plane_mm:
            issues.append("Distance to foot plane is outside the supported capture range.")
            instructions.append("Hold the phone above the foot at the guided capture distance.")

        confidence = min(metadata.depth_confidence, metadata.plane_confidence)
        if issues:
            return DepthQualityResult(
                depth_status="low_confidence",
                depth_mode=metadata.depth_mode,
                confidence=round(max(0.0, confidence), 4),
                issues=issues,
                instructions=instructions,
                can_support_scale=False,
            )
        return DepthQualityResult(
            depth_status="available",
            depth_mode=metadata.depth_mode,
            confidence=round(confidence, 4),
            issues=[],
            instructions=[],
            can_support_scale=True,
        )

    def normalize(self, depth_metadata: dict[str, Any] | DepthMetadata | None) -> DepthMetadata:
        if depth_metadata is None:
            return DepthMetadata()
        if isinstance(depth_metadata, DepthMetadata):
            return depth_metadata
        payload = dict(depth_metadata)
        floor_payload = payload.get("floor_plane") or {}
        intrinsics_payload = payload.get("camera_intrinsics") or {}
        intrinsics = self._intrinsics(intrinsics_payload)
        floor_plane = PlaneEstimate(
            normal=tuple(floor_payload.get("normal") or ()) or None,
            distance_to_floor_mm=self._float_or_none(
                floor_payload.get("distance_mm") or payload.get("distance_to_floor_mm")
            ),
            confidence=self._float_or_default(floor_payload.get("confidence"), 0.0),
        )
        return DepthMetadata(
            depth_available=bool(payload.get("depth_available")),
            depth_mode=str(payload.get("depth_mode") or "none"),
            camera_intrinsics=intrinsics,
            floor_plane=floor_plane,
            distance_to_floor_mm=self._float_or_none(payload.get("distance_to_floor_mm"))
            or floor_plane.distance_to_floor_mm,
            distance_to_foot_plane_mm=self._float_or_none(payload.get("distance_to_foot_plane_mm")),
            plane_confidence=self._float_or_default(
                payload.get("plane_confidence"),
                floor_plane.confidence,
            ),
            depth_confidence=self._float_or_default(payload.get("depth_confidence"), 0.0),
            calibrated=bool(payload.get("calibrated")),
            timestamp=payload.get("timestamp"),
            source_device=payload.get("source_device"),
            raw=payload.get("raw") or payload,
        )

    def _intrinsics(self, payload: dict[str, Any]) -> CameraIntrinsics:
        return CameraIntrinsics(
            fx=self._float_or_none(payload.get("fx") or payload.get("focal_length_x")),
            fy=self._float_or_none(payload.get("fy") or payload.get("focal_length_y")),
            cx=self._float_or_none(payload.get("cx") or payload.get("principal_point_x")),
            cy=self._float_or_none(payload.get("cy") or payload.get("principal_point_y")),
            width=self._int_or_none(payload.get("width") or payload.get("image_width")),
            height=self._int_or_none(payload.get("height") or payload.get("image_height")),
        )

    def _intrinsics_complete(self, intrinsics: CameraIntrinsics | None) -> bool:
        return bool(
            intrinsics
            and intrinsics.fx
            and intrinsics.fy
            and intrinsics.cx is not None
            and intrinsics.cy is not None
            and intrinsics.width
            and intrinsics.height
        )

    def _float_or_default(self, value: Any, default: float) -> float:
        parsed = self._float_or_none(value)
        return parsed if parsed is not None else default

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

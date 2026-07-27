from __future__ import annotations

from typing import Any

from app.services.depth.contracts import CameraIntrinsics, DepthMetadata, PlaneEstimate


class PlaceholderDepthProvider:
    def get_depth_map(self) -> Any | None:
        return None

    def get_camera_intrinsics(self) -> CameraIntrinsics | None:
        return None

    def get_plane_estimate(self) -> PlaneEstimate | None:
        return None

    def get_distance_to_floor(self) -> float | None:
        return None

    def get_confidence(self) -> float:
        return 0.0


class UploadedDepthMetadataProvider:
    def __init__(self, depth_metadata: DepthMetadata | None = None) -> None:
        self.depth_metadata = depth_metadata or DepthMetadata()

    def get_depth_map(self) -> Any | None:
        return self.depth_metadata.raw.get("depth_map") if self.depth_metadata.raw else None

    def get_camera_intrinsics(self) -> CameraIntrinsics | None:
        return self.depth_metadata.camera_intrinsics

    def get_plane_estimate(self) -> PlaneEstimate | None:
        return self.depth_metadata.floor_plane

    def get_distance_to_floor(self) -> float | None:
        return self.depth_metadata.distance_to_floor_mm

    def get_confidence(self) -> float:
        return min(self.depth_metadata.depth_confidence, self.depth_metadata.plane_confidence)


class FutureARCoreDepthProvider(PlaceholderDepthProvider):
    pass


class FutureARKitDepthProvider(PlaceholderDepthProvider):
    pass


class FutureMonocularDepthProvider(PlaceholderDepthProvider):
    pass

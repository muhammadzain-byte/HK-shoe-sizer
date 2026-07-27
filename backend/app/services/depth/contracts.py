from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class CameraIntrinsics:
    fx: float | None = None
    fy: float | None = None
    cx: float | None = None
    cy: float | None = None
    width: int | None = None
    height: int | None = None

    @property
    def focal_length_x(self) -> float | None:
        return self.fx

    @property
    def focal_length_y(self) -> float | None:
        return self.fy

    @property
    def principal_point_x(self) -> float | None:
        return self.cx

    @property
    def principal_point_y(self) -> float | None:
        return self.cy

    @property
    def image_width(self) -> int | None:
        return self.width

    @property
    def image_height(self) -> int | None:
        return self.height


@dataclass(frozen=True)
class PlaneEstimate:
    distance_to_floor_mm: float | None = None
    confidence: float = 0.0
    normal: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class DepthMetadata:
    depth_available: bool = False
    depth_mode: str = "none"
    camera_intrinsics: CameraIntrinsics | None = None
    floor_plane: PlaneEstimate | None = None
    distance_to_floor_mm: float | None = None
    distance_to_foot_plane_mm: float | None = None
    plane_confidence: float = 0.0
    depth_confidence: float = 0.0
    calibrated: bool = False
    timestamp: str | None = None
    source_device: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DepthQualityResult:
    depth_status: str
    depth_mode: str
    confidence: float
    issues: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    can_support_scale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth_status": self.depth_status,
            "depth_mode": self.depth_mode,
            "confidence": self.confidence,
            "issues": self.issues,
            "instructions": self.instructions,
            "can_support_scale": self.can_support_scale,
        }


@dataclass(frozen=True)
class DepthScaleEvidence:
    can_estimate_scale: bool
    pixels_per_mm: float | None = None
    mm_per_pixel: float | None = None
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_estimate_scale": self.can_estimate_scale,
            "pixels_per_mm": self.pixels_per_mm,
            "mm_per_pixel": self.mm_per_pixel,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "issues": self.issues,
        }


@dataclass(frozen=True)
class DepthProviderResult:
    depth_metadata: DepthMetadata
    quality: DepthQualityResult
    raw_depth_map: Any | None = None


class DepthMapProvider(Protocol):
    def get_depth_map(self) -> Any | None:
        ...

    def get_camera_intrinsics(self) -> CameraIntrinsics | None:
        ...

    def get_plane_estimate(self) -> PlaneEstimate | None:
        ...

    def get_distance_to_floor(self) -> float | None:
        ...

    def get_confidence(self) -> float:
        ...

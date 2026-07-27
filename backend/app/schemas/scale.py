from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ScaleStatus = Literal["available", "low_confidence", "unavailable", "needs_reference"]
ScaleMode = Literal[
    "reference_object",
    "calibration_mat",
    "ar_depth",
    "device_camera_model",
    "monocular_depth_model",
    "unavailable",
]


class ScaleBoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ReferenceObjectInput(BaseModel):
    type: Literal["credit_card", "a4_paper", "calibration_card", "custom_object"]
    reference_mode: Literal["credit_card", "a4_paper", "calibration_card", "custom_object"] | None = None
    known_width_mm: float | None = Field(default=None, gt=0)
    known_height_mm: float | None = Field(default=None, gt=0)
    bbox: ScaleBoundingBox
    polygon: list[dict[str, float]] | None = None
    detection_confidence: float = Field(ge=0, le=1)
    same_plane_confidence: float | None = Field(default=None, ge=0, le=1)
    distortion_score: float | None = Field(default=None, ge=0, le=1)
    source: Literal["manual", "auto_detected", "user_adjusted"] = "manual"


class CalibrationMatInput(BaseModel):
    marker_spacing_mm: float | None = Field(default=None, gt=0)
    detected_markers: list[dict[str, float]] = Field(default_factory=list)
    detection_confidence: float = Field(default=0.0, ge=0, le=1)


class CameraIntrinsicsInput(BaseModel):
    fx: float | None = None
    fy: float | None = None
    cx: float | None = None
    cy: float | None = None
    width: int | None = None
    height: int | None = None
    focal_length_x: float | None = None
    focal_length_y: float | None = None
    principal_point_x: float | None = None
    principal_point_y: float | None = None
    image_width: int | None = None
    image_height: int | None = None


class FloorPlaneInput(BaseModel):
    normal: list[float] = Field(default_factory=list)
    distance_mm: float | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class DepthMetadataInput(BaseModel):
    depth_available: bool = False
    depth_mode: Literal["arcore", "arkit", "lidar", "monocular", "uploaded_depth", "none"] = "none"
    camera_intrinsics: CameraIntrinsicsInput | dict[str, Any] | None = None
    floor_plane: FloorPlaneInput | dict[str, Any] | None = None
    distance_to_floor_mm: float | None = None
    distance_to_foot_plane_mm: float | None = None
    plane_confidence: float = Field(default=0.0, ge=0, le=1)
    depth_confidence: float = Field(default=0.0, ge=0, le=1)
    calibrated: bool = False
    timestamp: str | None = None
    source_device: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


from app.schemas.reference_object import ReferenceObjectDetectionOptions  # noqa: E402


class ScaleEstimateRequest(BaseModel):
    reference_object: ReferenceObjectInput | None = None
    reference_object_detection: ReferenceObjectDetectionOptions | None = None
    calibration_mat: CalibrationMatInput | None = None
    depth_metadata: DepthMetadataInput | None = None
    device_metadata: dict[str, Any] | None = None
    image_metadata: dict[str, Any] | None = None


class RealWorldMeasurementResult(BaseModel):
    foot_length_mm: float | None = None
    foot_width_mm: float | None = None
    scale_status: str
    measurement_status: str
    can_recommend_size: bool = False


class ScaleEstimateResponse(BaseModel):
    scale_status: ScaleStatus
    scale_mode: ScaleMode
    pixels_per_mm: float | None = None
    mm_per_pixel: float | None = None
    confidence: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    real_world_measurement: RealWorldMeasurementResult | None = None


class ScaleEstimateRead(ScaleEstimateResponse):
    id: UUID
    user_id: UUID
    foot_scan_id: UUID
    foot_measurement_id: UUID | None = None
    capture_session_id: UUID | None = None
    foot_length_mm: float | None = None
    foot_width_mm: float | None = None
    can_recommend_size: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

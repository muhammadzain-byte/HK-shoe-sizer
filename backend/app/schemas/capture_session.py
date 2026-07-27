from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceOrientationPayload(BaseModel):
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None


class CaptureDeviceMetadata(BaseModel):
    user_agent: str | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    video_width: int | None = None
    video_height: int | None = None
    device_pixel_ratio: float | None = None
    facing_mode: str | None = None
    orientation: DeviceOrientationPayload | None = None
    motion: dict[str, Any] | None = None
    timestamp: str | None = None
    reference_mode: str | None = None
    capture_mode: str = "browser_guidance"
    ar_evidence: dict[str, Any] | None = None


class CaptureFrameQualityRead(BaseModel):
    blur_score: float | None = None
    lighting_score: float | None = None
    overexposure_score: float | None = None


class CaptureFootVisibilityRead(BaseModel):
    foot_detected: bool | None = None
    one_foot_only: bool | None = None
    toes_visible: bool | None = None
    heel_visible: bool | None = None
    full_foot_visible: bool | None = None
    lower_leg_ratio: float | None = None
    toe_margin_ratio: float | None = None
    heel_margin_ratio: float | None = None
    side_margin_ratio: float | None = None


class CapturePoseQualityRead(BaseModel):
    top_down_score: float | None = None
    rotation_angle_degrees: float | None = None
    perspective_risk: float | None = None
    foot_flatness_risk: float | None = None


class CaptureDistanceQualityRead(BaseModel):
    foot_frame_coverage: float | None = None
    too_close: bool | None = None
    too_far: bool | None = None
    distance_confidence: float | None = None


class CaptureDeviceMetadataRead(CaptureDeviceMetadata):
    browser: str | None = None
    os: str | None = None
    device_type: str | None = None
    device_family: str | None = None


class CaptureSessionCreate(BaseModel):
    foot_scan_id: UUID | None = None
    uploaded_image_id: UUID | None = None
    device_metadata: CaptureDeviceMetadata | dict[str, Any] | None = None
    capture_quality: dict[str, Any] = Field(default_factory=dict)


class CaptureSessionAttachRequest(BaseModel):
    foot_scan_id: UUID | None = None
    uploaded_image_id: UUID | None = None


class CaptureSessionRead(BaseModel):
    id: UUID
    user_id: UUID
    foot_scan_id: UUID | None = None
    uploaded_image_id: UUID | None = None
    capture_status: str
    capture_quality_score: float
    primary_instruction: str | None = None
    issues: list[str]
    instructions: list[str]
    frame_quality: CaptureFrameQualityRead
    foot_visibility: CaptureFootVisibilityRead
    pose_quality: CapturePoseQualityRead
    distance_quality: CaptureDistanceQualityRead
    device_metadata: CaptureDeviceMetadataRead
    created_at: datetime


class CaptureSessionListItem(CaptureSessionRead):
    pass


class CaptureSessionListResponse(BaseModel):
    items: list[CaptureSessionListItem]
    total: int
    limit: int
    offset: int

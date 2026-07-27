from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class FootBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class MeasurementPointResponse(BaseModel):
    x: float
    y: float


class WidthPointsResponse(BaseModel):
    left: MeasurementPointResponse
    right: MeasurementPointResponse


class MeasurementResponse(BaseModel):
    measurement_status: str
    foot_length_pixels: float
    foot_width_pixels: float
    heel_point: MeasurementPointResponse
    toe_point: MeasurementPointResponse
    width_points: WidthPointsResponse
    confidence_score: float


class AIProcessResponse(BaseModel):
    scan_id: UUID
    status: str
    message: str
    valid: bool | None = None
    issues: list[str] = []
    foot_count: int | None = None
    segmentation_confidence: float | None = None
    foot_bbox: FootBoundingBox | None = None


class AIStatusResponse(BaseModel):
    scan_id: UUID
    status: str
    processing_error: str | None = None
    validation_status: str | None = None
    validation_issues: list[str] | None = None


class ImageValidationResponse(BaseModel):
    valid: bool
    issues: list[str]
    foot_count: int | None = None
    segmentation_confidence: float | None = None
    foot_bbox: FootBoundingBox | None = None


class CaptureFrameQuality(BaseModel):
    blur_score: float
    lighting_score: float
    overexposure_score: float


class CaptureFootVisibility(BaseModel):
    foot_detected: bool
    one_foot_only: bool
    toes_visible: bool
    heel_visible: bool
    full_foot_visible: bool
    lower_leg_ratio: float
    toe_margin_ratio: float
    heel_margin_ratio: float
    side_margin_ratio: float


class CapturePoseQuality(BaseModel):
    top_down_score: float
    rotation_angle_degrees: float
    perspective_risk: float
    foot_flatness_risk: float


class CaptureDistanceQuality(BaseModel):
    foot_frame_coverage: float
    too_close: bool
    too_far: bool
    distance_confidence: float


class CaptureGuidance(BaseModel):
    primary_instruction: str
    secondary_instructions: list[str] = []


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
    motion: dict | None = None
    timestamp: str | None = None
    reference_mode: str | None = None
    # Native capture clients may provide ARCore/ARKit evidence here. Browser
    # clients must report browser_guidance and never imply metric AR support.
    capture_mode: str = "browser_guidance"
    ar_evidence: dict | None = None


class CaptureQualityResult(BaseModel):
    success: bool | None = None
    stage: str | None = None
    status: str | None = None
    capture_status: str
    score: float
    issues: list[str]
    instructions: list[str]
    frame_quality: CaptureFrameQuality
    foot_visibility: CaptureFootVisibility
    pose_quality: CapturePoseQuality
    distance_quality: CaptureDistanceQuality
    guidance: CaptureGuidance
    stability: dict | None = None


class CaptureQualityScanRequest(BaseModel):
    device_metadata: CaptureDeviceMetadata | None = None
    persist_session: bool = False
    uploaded_image_id: UUID | None = None


class ShoeRecommendationRead(BaseModel):
    region: str
    size_value: str
    width_category: str | None
    brand: str | None
    confidence_score: Decimal | None
    rationale: str | None

    model_config = {"from_attributes": True}


class AIResultsResponse(BaseModel):
    scan_id: UUID
    length_mm: Decimal | None
    width_mm: Decimal | None
    arch_height_mm: Decimal | None
    confidence_score: Decimal | None
    recommendations: list[ShoeRecommendationRead]

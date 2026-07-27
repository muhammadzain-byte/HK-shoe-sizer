from typing import Literal

from pydantic import BaseModel, Field


ReferenceObjectMode = Literal["none", "credit_card", "a4_paper", "calibration_card", "custom_object"]
ReferenceObjectSource = Literal["manual", "auto_detected", "user_adjusted"]


class ReferenceObjectBoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ReferenceObjectPoint(BaseModel):
    x: float
    y: float


class ReferenceObjectDetectionOptions(BaseModel):
    enabled: bool = False
    reference_mode: ReferenceObjectMode = "none"
    known_width_mm: float | None = Field(default=None, gt=0)
    known_height_mm: float | None = Field(default=None, gt=0)
    manual_bbox: ReferenceObjectBoundingBox | None = None
    manual_polygon: list[ReferenceObjectPoint] | None = None
    detection_confidence: float | None = Field(default=None, ge=0, le=1)
    same_plane_confidence: float | None = Field(default=None, ge=0, le=1)
    distortion_score: float | None = Field(default=None, ge=0, le=1)
    source: ReferenceObjectSource = "manual"


class ReferenceObjectDetectionRequest(BaseModel):
    reference_mode: ReferenceObjectMode
    known_width_mm: float | None = Field(default=None, gt=0)
    known_height_mm: float | None = Field(default=None, gt=0)
    manual_bbox: ReferenceObjectBoundingBox | None = None
    manual_polygon: list[ReferenceObjectPoint] | None = None
    detection_confidence: float | None = Field(default=None, ge=0, le=1)
    same_plane_confidence: float | None = Field(default=None, ge=0, le=1)
    distortion_score: float | None = Field(default=None, ge=0, le=1)
    source: ReferenceObjectSource = "manual"


class ReferenceObjectDetectionResponse(BaseModel):
    detected: bool
    reference_mode: ReferenceObjectMode
    bbox: ReferenceObjectBoundingBox | None = None
    polygon: list[ReferenceObjectPoint] | None = None
    confidence: float
    distortion_score: float
    same_plane_confidence: float
    source: ReferenceObjectSource
    reference_object: dict | None = None
    issues: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)

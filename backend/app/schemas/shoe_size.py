from typing import Literal

from pydantic import BaseModel, Field


class ShoeFitInput(BaseModel):
    fit_preference: Literal["snug", "regular", "relaxed"] = "regular"
    shoe_type: Literal["flat", "heel", "sandal", "sneaker", "khussa", "formal"] = "flat"


class ShoeSizeRequest(ShoeFitInput):
    region: Literal["EU", "US", "UK", "PK"]
    gender: str = "women"
    foot_length_mm: float | None = None
    foot_width_mm: float | None = None
    measurement_status: str = ""
    scale_status: str = ""
    scale_confidence: float = Field(default=0.0, ge=0, le=1)
    capture_status: str | None = None


class ShoeSizeAlternative(BaseModel):
    size: str
    reason: str


class ShoeSizeReason(BaseModel):
    code: str
    message: str


class ShoeSizeResponse(BaseModel):
    recommendation_status: Literal[
        "recommended",
        "blocked_by_capture_quality",
        "blocked_by_measurement_quality",
        "blocked_by_scale",
        "unsupported",
    ]
    recommended_size: str | None = None
    size_system: str
    width_category: Literal["narrow", "regular", "wide"] | None = None
    confidence: float
    reasoning: list[ShoeSizeReason] = Field(default_factory=list)
    alternate_sizes: list[ShoeSizeAlternative] = Field(default_factory=list)
    fit_notes: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None

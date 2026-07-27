from typing import Any

from pydantic import BaseModel, Field

from app.schemas.reference_object import ReferenceObjectDetectionOptions
from app.schemas.scale import DepthMetadataInput, ReferenceObjectInput
from app.schemas.shoe_size import ShoeSizeRequest, ShoeSizeResponse


class FullPipelineRequest(BaseModel):
    reference_object: ReferenceObjectInput | None = None
    reference_object_detection: ReferenceObjectDetectionOptions | None = None
    depth_metadata: DepthMetadataInput | None = None
    shoe_size_request: ShoeSizeRequest | None = None
    run_shoe_size: bool = False


class PipelineStageResult(BaseModel):
    stage_status: str
    data: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class FullPipelineResponse(BaseModel):
    overall_status: str
    capture_quality: PipelineStageResult
    measurement: PipelineStageResult
    landmark_validation: PipelineStageResult
    scale_estimate: PipelineStageResult
    shoe_recommendation: ShoeSizeResponse | None = None
    next_action: str
    user_message: str
    debug: dict[str, Any] = Field(default_factory=dict)

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReferenceBBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ValidationCaseBase(BaseModel):
    case_id: str = Field(min_length=1, max_length=64)
    case_label: str | None = None
    device_label: str | None = None
    device_os: str | None = None
    browser: str | None = None
    camera_type: str | None = None
    foot_side: str | None = Field(default=None, pattern="^(left|right|both|none|unknown)$")
    capture_scenario: str | None = None
    ground_truth_length_mm: float | None = Field(default=None, gt=0)
    ground_truth_width_mm: float | None = Field(default=None, gt=0)
    ground_truth_source: str | None = None
    reference_mode: str = Field(default="none")
    reference_width_mm: float | None = Field(default=None, gt=0)
    reference_height_mm: float | None = Field(default=None, gt=0)
    reference_bbox_x: float | None = Field(default=None, ge=0)
    reference_bbox_y: float | None = Field(default=None, ge=0)
    reference_bbox_width: float | None = Field(default=None, gt=0)
    reference_bbox_height: float | None = Field(default=None, gt=0)
    reference_polygon_json: list[dict] | None = None
    notes: str | None = None


class ValidationCaseCreate(ValidationCaseBase):
    image_upload_id: UUID | None = None
    scan_id: UUID | None = None
    capture_session_id: UUID | None = None


class ValidationCaseUpdate(BaseModel):
    case_label: str | None = None
    image_upload_id: UUID | None = None
    scan_id: UUID | None = None
    capture_session_id: UUID | None = None
    device_label: str | None = None
    device_os: str | None = None
    browser: str | None = None
    camera_type: str | None = None
    foot_side: str | None = Field(default=None, pattern="^(left|right|both|none|unknown)$")
    capture_scenario: str | None = None
    ground_truth_length_mm: float | None = Field(default=None, gt=0)
    ground_truth_width_mm: float | None = Field(default=None, gt=0)
    ground_truth_source: str | None = None
    reference_mode: str | None = None
    reference_width_mm: float | None = Field(default=None, gt=0)
    reference_height_mm: float | None = Field(default=None, gt=0)
    reference_bbox_x: float | None = Field(default=None, ge=0)
    reference_bbox_y: float | None = Field(default=None, ge=0)
    reference_bbox_width: float | None = Field(default=None, gt=0)
    reference_bbox_height: float | None = Field(default=None, gt=0)
    reference_polygon_json: list[dict] | None = None
    status: str | None = None
    notes: str | None = None


class ValidationCaseAttachUpload(BaseModel):
    image_upload_id: UUID


class ValidationCaseLinkScan(BaseModel):
    scan_id: UUID
    capture_session_id: UUID | None = None


class ValidationCaseRead(ValidationCaseBase):
    id: UUID
    user_id: UUID
    image_upload_id: UUID | None
    scan_id: UUID | None
    capture_session_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ValidationCaseListResponse(BaseModel):
    items: list[ValidationCaseRead]
    total: int
    limit: int
    offset: int


class ValidationCaseSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_device_os: dict[str, int]
    by_capture_scenario: dict[str, int]
    benchmark_ready_count: int
    benchmark_completed_count: int


class ValidationBenchmarkResultRead(BaseModel):
    id: UUID
    validation_case_id: UUID
    scan_id: UUID | None
    measured_length_mm: float | None
    measured_width_mm: float | None
    ground_truth_length_mm: float | None
    ground_truth_width_mm: float | None
    length_error_mm: float | None
    width_error_mm: float | None
    length_abs_error_mm: float | None
    width_abs_error_mm: float | None
    length_error_percent: float | None
    width_error_percent: float | None
    capture_status: str | None
    measurement_status: str | None
    scale_status: str | None
    size_status: str | None
    recommended_size_system: str | None
    recommended_size: str | None
    failure_stage: str | None
    failure_reasons_json: list[str] | None
    pipeline_output_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}

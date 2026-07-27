from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ExternalDatasetSplit = Literal["train", "val", "test", "unknown"]
LicenseStatus = Literal["unknown", "reviewed", "restricted"]


class ExternalDatasetRegistryEntry(BaseModel):
    id: str
    name: str
    repo_url: str | None = None
    project_url: str | None = None
    paper_url: str | None = None
    dataset_type: list[str] = Field(default_factory=list)
    intended_use: list[str] = Field(default_factory=list)
    not_for: list[str] = Field(default_factory=list)
    download_policy: str
    license_review_required: bool = True
    local_raw_dir: str
    local_processed_dir: str


class ExternalDatasetSample(BaseModel):
    sample_id: str
    dataset_id: str
    split: ExternalDatasetSplit = "unknown"
    image_path: str | None = None
    mask_path: str | None = None
    normal_path: str | None = None
    keypoints_path: str | None = None
    dense_correspondence_path: str | None = None
    mesh_path: str | None = None
    point_cloud_path: str | None = None
    camera_metadata_path: str | None = None
    subject_id: str | None = None
    view_id: str | None = None
    foot_side: str | None = None
    available_labels: list[str] = Field(default_factory=list)
    research_use_only: bool = True
    notes: str = ""


class ExternalDatasetManifest(BaseModel):
    dataset_id: str
    source_url: str | None = None
    paper_url: str | None = None
    local_root: str | None = None
    license_status: LicenseStatus = "unknown"
    sample_count: int = 0
    file_inventory: dict[str, int] = Field(default_factory=dict)
    detected_file_types: list[str] = Field(default_factory=list)
    label_types: list[str] = Field(default_factory=list)
    research_use_only: bool = True
    issues: list[str] = Field(default_factory=list)
    samples: list[ExternalDatasetSample] = Field(default_factory=list)


class ExternalDatasetInspectionResult(BaseModel):
    dataset_id: str
    local_raw_dir: str
    local_processed_dir: str
    raw_exists: bool
    processed_exists: bool
    raw_file_count: int = 0
    processed_file_count: int = 0
    detected_file_types: list[str] = Field(default_factory=list)
    label_types: list[str] = Field(default_factory=list)
    research_use_only: bool = True
    issues: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)


class ExternalDatasetConversionResult(BaseModel):
    dataset_id: str
    success: bool
    manifest_path: str | None = None
    sample_count: int = 0
    issues: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PresignUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern="^image/(jpeg|jpg|png|webp)$")
    byte_size: int = Field(gt=0, le=15_000_000)
    foot_scan_id: UUID | None = None


class PresignUploadResponse(BaseModel):
    image_id: UUID
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    object_key: str
    expires_in_seconds: int


class CompleteUploadRequest(BaseModel):
    image_id: UUID
    foot_scan_id: UUID | None = None
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadedImageRead(BaseModel):
    id: UUID
    user_id: UUID
    foot_scan_id: UUID | None
    bucket: str
    object_key: str
    content_type: str
    byte_size: int | None
    checksum_sha256: str | None
    upload_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocalUploadResponse(BaseModel):
    image_id: UUID
    file_url: str
    storage_path: str
    mime_type: str
    size_bytes: int

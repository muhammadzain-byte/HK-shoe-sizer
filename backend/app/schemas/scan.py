from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.upload import UploadedImageRead


class FootScanCreate(BaseModel):
    foot_side: str = Field(default="unknown", pattern="^(left|right|unknown)$")


class FootScanUpdate(BaseModel):
    foot_side: str | None = Field(default=None, pattern="^(left|right|unknown)$")


class FootScanRead(BaseModel):
    id: UUID
    user_id: UUID
    foot_side: str
    status: str
    length_mm: Decimal | None
    width_mm: Decimal | None
    arch_height_mm: Decimal | None
    confidence_score: Decimal | None
    validation_status: str | None
    validation_issues: list[str] | None
    processing_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScanHistoryItem(BaseModel):
    scan: FootScanRead
    recommendation_count: int = 0
    uploaded_image_count: int = 0


class ScanDetailRead(FootScanRead):
    uploaded_images: list[UploadedImageRead] = Field(default_factory=list)
    recommendation_count: int = 0


class PaginatedScanHistory(BaseModel):
    items: list[ScanHistoryItem]
    total: int
    limit: int
    offset: int

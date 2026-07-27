from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisJobCreate(BaseModel):
    job_type: Literal["measurement"] = "measurement"


class AnalysisJobRead(BaseModel):
    id: UUID
    scan_id: UUID
    job_type: str
    status: str
    progress: int = Field(ge=0, le=100)
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scale_estimate import ScaleEstimate
from app.models.user import User
from app.services.scale_estimation_service import ScaleEstimateResult


class ScaleEstimatePersistenceService:
    def __init__(self, db: Session):
        self.db = db

    def persist_estimate(
        self,
        user: User,
        foot_scan_id: UUID,
        estimate: ScaleEstimateResult,
        foot_measurement_id: UUID | None = None,
        capture_session_id: UUID | None = None,
    ) -> ScaleEstimate:
        real_world = estimate.real_world_measurement
        record = ScaleEstimate(
            user_id=user.id,
            foot_scan_id=foot_scan_id,
            foot_measurement_id=foot_measurement_id,
            capture_session_id=capture_session_id,
            scale_status=estimate.scale_status,
            scale_mode=estimate.scale_mode,
            pixels_per_mm=estimate.pixels_per_mm,
            mm_per_pixel=estimate.mm_per_pixel,
            confidence=estimate.confidence,
            evidence=estimate.evidence,
            issues=estimate.issues,
            instructions=estimate.instructions,
            foot_length_mm=real_world.foot_length_mm if real_world else None,
            foot_width_mm=real_world.foot_width_mm if real_world else None,
            can_recommend_size=False,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_scale_estimate(self, user: User, scale_estimate_id: UUID) -> ScaleEstimate:
        estimate = self.db.scalar(
            select(ScaleEstimate).where(
                ScaleEstimate.id == scale_estimate_id,
                ScaleEstimate.user_id == user.id,
            )
        )
        if not estimate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scale estimate not found.")
        return estimate

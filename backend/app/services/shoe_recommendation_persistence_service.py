from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shoe_recommendation import ShoeRecommendation
from app.models.user import User
from app.schemas.shoe_size import ShoeSizeRequest, ShoeSizeResponse


class ShoeRecommendationPersistenceService:
    def __init__(self, db: Session):
        self.db = db

    def persist_recommendation(
        self,
        user: User,
        foot_scan_id: UUID,
        request: ShoeSizeRequest,
        response: ShoeSizeResponse,
        scale_estimate_id: UUID | None = None,
    ) -> ShoeRecommendation:
        record = ShoeRecommendation(
            user_id=user.id,
            foot_scan_id=foot_scan_id,
            scale_estimate_id=scale_estimate_id,
            region=request.region,
            gender=request.gender,
            shoe_type=request.shoe_type,
            fit_preference=request.fit_preference,
            recommendation_status=response.recommendation_status,
            recommended_size=response.recommended_size,
            size_system=response.size_system,
            size_value=response.recommended_size or "",
            width_category=response.width_category,
            brand=None,
            confidence=response.confidence,
            confidence_score=response.confidence,
            reasoning=[reason.model_dump() for reason in response.reasoning],
            alternate_sizes=[alternate.model_dump() for alternate in response.alternate_sizes],
            fit_notes=response.fit_notes,
            blocked_reason=response.blocked_reason,
            rationale="; ".join(reason.message for reason in response.reasoning),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_recommendation(self, user: User, recommendation_id: UUID) -> ShoeRecommendation:
        recommendation = self.db.scalar(
            select(ShoeRecommendation).where(
                ShoeRecommendation.id == recommendation_id,
                ShoeRecommendation.user_id == user.id,
            )
        )
        if not recommendation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shoe recommendation not found.",
            )
        return recommendation

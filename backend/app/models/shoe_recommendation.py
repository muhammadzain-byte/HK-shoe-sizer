from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ShoeRecommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shoe_recommendations"

    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    foot_scan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("foot_scans.id"), nullable=False
    )
    scale_estimate_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scale_estimates.id")
    )
    region: Mapped[str] = mapped_column(String(16), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(32))
    shoe_type: Mapped[str | None] = mapped_column(String(64))
    fit_preference: Mapped[str | None] = mapped_column(String(64))
    recommendation_status: Mapped[str | None] = mapped_column(String(64))
    recommended_size: Mapped[str | None] = mapped_column(String(32))
    size_system: Mapped[str | None] = mapped_column(String(32))
    size_value: Mapped[str] = mapped_column(String(20), nullable=False)
    width_category: Mapped[str | None] = mapped_column(String(32))
    brand: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    reasoning: Mapped[list | None] = mapped_column(JSON)
    alternate_sizes: Mapped[list | None] = mapped_column(JSON)
    fit_notes: Mapped[list | None] = mapped_column(JSON)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="shoe_recommendations")
    foot_scan = relationship("FootScan", back_populates="recommendations")
    scale_estimate = relationship("ScaleEstimate", back_populates="shoe_recommendations")

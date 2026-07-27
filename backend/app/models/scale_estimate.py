from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class ScaleEstimate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scale_estimates"
    __table_args__ = (
        Index("ix_scale_estimates_user_id", "user_id"),
        Index("ix_scale_estimates_foot_scan_id", "foot_scan_id"),
        Index("ix_scale_estimates_capture_session_id", "capture_session_id"),
        Index("ix_scale_estimates_scale_status", "scale_status"),
        Index("ix_scale_estimates_scale_mode", "scale_mode"),
        Index("ix_scale_estimates_created_at", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    foot_scan_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("foot_scans.id"), nullable=False)
    foot_measurement_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("foot_measurements.id")
    )
    capture_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("capture_sessions.id")
    )

    scale_status: Mapped[str] = mapped_column(String(32), nullable=False)
    scale_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    pixels_per_mm: Mapped[float | None] = mapped_column(Float)
    mm_per_pixel: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict | None] = mapped_column(JSON)
    issues: Mapped[list[str] | None] = mapped_column(JSON)
    instructions: Mapped[list[str] | None] = mapped_column(JSON)

    foot_length_mm: Mapped[float | None] = mapped_column(Float)
    foot_width_mm: Mapped[float | None] = mapped_column(Float)
    can_recommend_size: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="scale_estimates")
    foot_scan = relationship("FootScan", back_populates="scale_estimates")
    foot_measurement = relationship("FootMeasurement", back_populates="scale_estimates")
    capture_session = relationship("CaptureSession", back_populates="scale_estimates")
    shoe_recommendations = relationship("ShoeRecommendation", back_populates="scale_estimate")

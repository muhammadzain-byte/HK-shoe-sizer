from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class FootScan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "foot_scans"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    foot_side: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False, index=True)
    length_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    arch_height_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    validation_status: Mapped[str | None] = mapped_column(String(32))
    validation_issues: Mapped[list[str] | None] = mapped_column(JSON)
    processing_error: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="scans")
    uploaded_images = relationship("UploadedImage", back_populates="foot_scan")
    recommendations = relationship("ShoeRecommendation", back_populates="foot_scan")
    measurements = relationship("FootMeasurement", back_populates="scan")
    capture_sessions = relationship("CaptureSession", back_populates="foot_scan")
    scale_estimates = relationship("ScaleEstimate", back_populates="foot_scan")
    validation_cases = relationship("ValidationCase", back_populates="scan")
    validation_benchmark_results = relationship("ValidationBenchmarkResult", back_populates="scan")

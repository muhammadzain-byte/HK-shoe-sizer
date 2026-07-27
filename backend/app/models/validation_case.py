from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ValidationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "validation_cases"
    __table_args__ = (
        Index("ix_validation_cases_user_id", "user_id"),
        Index("ix_validation_cases_case_id", "case_id"),
        Index("ix_validation_cases_scan_id", "scan_id"),
        Index("ix_validation_cases_status", "status"),
        Index("ix_validation_cases_device_os", "device_os"),
        Index("ix_validation_cases_capture_scenario", "capture_scenario"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_label: Mapped[str | None] = mapped_column(String(255))
    image_upload_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("uploaded_images.id"))
    scan_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("foot_scans.id"))
    capture_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("capture_sessions.id")
    )
    device_label: Mapped[str | None] = mapped_column(String(255))
    device_os: Mapped[str | None] = mapped_column(String(128))
    browser: Mapped[str | None] = mapped_column(String(128))
    camera_type: Mapped[str | None] = mapped_column(String(128))
    foot_side: Mapped[str | None] = mapped_column(String(16))
    capture_scenario: Mapped[str | None] = mapped_column(String(128))
    ground_truth_length_mm: Mapped[float | None] = mapped_column(Float)
    ground_truth_width_mm: Mapped[float | None] = mapped_column(Float)
    ground_truth_source: Mapped[str | None] = mapped_column(String(128))
    reference_mode: Mapped[str] = mapped_column(String(64), default="none", nullable=False)
    reference_width_mm: Mapped[float | None] = mapped_column(Float)
    reference_height_mm: Mapped[float | None] = mapped_column(Float)
    reference_bbox_x: Mapped[float | None] = mapped_column(Float)
    reference_bbox_y: Mapped[float | None] = mapped_column(Float)
    reference_bbox_width: Mapped[float | None] = mapped_column(Float)
    reference_bbox_height: Mapped[float | None] = mapped_column(Float)
    reference_polygon_json: Mapped[list[dict] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="validation_cases")
    image_upload = relationship("UploadedImage", back_populates="validation_cases")
    scan = relationship("FootScan", back_populates="validation_cases")
    capture_session = relationship("CaptureSession", back_populates="validation_cases")
    benchmark_results = relationship(
        "ValidationBenchmarkResult",
        back_populates="validation_case",
        cascade="all, delete-orphan",
    )

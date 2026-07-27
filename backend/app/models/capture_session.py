from uuid import UUID

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CaptureSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capture_sessions"
    __table_args__ = (
        Index("ix_capture_sessions_user_id", "user_id"),
        Index("ix_capture_sessions_foot_scan_id", "foot_scan_id"),
        Index("ix_capture_sessions_uploaded_image_id", "uploaded_image_id"),
        Index("ix_capture_sessions_capture_status", "capture_status"),
        Index("ix_capture_sessions_created_at", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    foot_scan_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("foot_scans.id"))
    uploaded_image_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("uploaded_images.id")
    )

    capture_status: Mapped[str] = mapped_column(String(32), nullable=False)
    capture_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    primary_instruction: Mapped[str | None] = mapped_column(Text)
    issues: Mapped[list[str] | None] = mapped_column(JSON)
    instructions: Mapped[list[str] | None] = mapped_column(JSON)

    blur_score: Mapped[float | None] = mapped_column(Float)
    lighting_score: Mapped[float | None] = mapped_column(Float)
    overexposure_score: Mapped[float | None] = mapped_column(Float)

    foot_detected: Mapped[bool | None] = mapped_column(Boolean)
    one_foot_only: Mapped[bool | None] = mapped_column(Boolean)
    toes_visible: Mapped[bool | None] = mapped_column(Boolean)
    heel_visible: Mapped[bool | None] = mapped_column(Boolean)
    full_foot_visible: Mapped[bool | None] = mapped_column(Boolean)
    lower_leg_ratio: Mapped[float | None] = mapped_column(Float)
    toe_margin_ratio: Mapped[float | None] = mapped_column(Float)
    heel_margin_ratio: Mapped[float | None] = mapped_column(Float)
    side_margin_ratio: Mapped[float | None] = mapped_column(Float)

    top_down_score: Mapped[float | None] = mapped_column(Float)
    rotation_angle_degrees: Mapped[float | None] = mapped_column(Float)
    perspective_risk: Mapped[float | None] = mapped_column(Float)
    foot_flatness_risk: Mapped[float | None] = mapped_column(Float)

    foot_frame_coverage: Mapped[float | None] = mapped_column(Float)
    too_close: Mapped[bool | None] = mapped_column(Boolean)
    too_far: Mapped[bool | None] = mapped_column(Boolean)
    distance_confidence: Mapped[float | None] = mapped_column(Float)

    user_agent: Mapped[str | None] = mapped_column(Text)
    browser: Mapped[str | None] = mapped_column(String(128))
    os: Mapped[str | None] = mapped_column(String(128))
    device_type: Mapped[str | None] = mapped_column(String(128))
    device_family: Mapped[str | None] = mapped_column(String(128))

    viewport_width: Mapped[int | None] = mapped_column(Integer)
    viewport_height: Mapped[int | None] = mapped_column(Integer)
    video_width: Mapped[int | None] = mapped_column(Integer)
    video_height: Mapped[int | None] = mapped_column(Integer)
    device_pixel_ratio: Mapped[float | None] = mapped_column(Float)
    facing_mode: Mapped[str | None] = mapped_column(String(64))

    orientation_alpha: Mapped[float | None] = mapped_column(Float)
    orientation_beta: Mapped[float | None] = mapped_column(Float)
    orientation_gamma: Mapped[float | None] = mapped_column(Float)

    motion: Mapped[dict | None] = mapped_column(JSON)
    raw_device_metadata: Mapped[dict | None] = mapped_column(JSON)
    raw_capture_quality_result: Mapped[dict | None] = mapped_column(JSON)

    user = relationship("User", back_populates="capture_sessions")
    foot_scan = relationship("FootScan", back_populates="capture_sessions")
    uploaded_image = relationship("UploadedImage", back_populates="capture_sessions")
    scale_estimates = relationship("ScaleEstimate", back_populates="capture_session")
    validation_cases = relationship("ValidationCase", back_populates="capture_session")

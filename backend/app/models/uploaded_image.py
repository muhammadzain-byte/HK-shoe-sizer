from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UploadedImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_images"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    foot_scan_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("foot_scans.id"))
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    upload_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)

    user = relationship("User", back_populates="uploaded_images")
    foot_scan = relationship("FootScan", back_populates="uploaded_images")
    capture_sessions = relationship("CaptureSession", back_populates="uploaded_image")
    validation_cases = relationship("ValidationCase", back_populates="image_upload")

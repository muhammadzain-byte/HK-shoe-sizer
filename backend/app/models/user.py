from datetime import date

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str] = mapped_column(String(32), default="woman", nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    country_code: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    scans = relationship("FootScan", back_populates="user", cascade="all, delete-orphan")
    uploaded_images = relationship("UploadedImage", back_populates="user")
    capture_sessions = relationship("CaptureSession", back_populates="user", cascade="all, delete-orphan")
    scale_estimates = relationship("ScaleEstimate", back_populates="user", cascade="all, delete-orphan")
    shoe_recommendations = relationship("ShoeRecommendation", back_populates="user")
    validation_cases = relationship("ValidationCase", back_populates="user", cascade="all, delete-orphan")

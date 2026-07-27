from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class FootMeasurement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "foot_measurements"

    scan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("foot_scans.id"), nullable=False, index=True
    )
    model_name: Mapped[str | None] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(50))
    foot_length_pixels: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    foot_width_pixels: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    heel_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    heel_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    toe_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    toe_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    width_left_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    width_left_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    width_right_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    width_right_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    measurement_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now(), nullable=False)

    scan = relationship("FootScan", back_populates="measurements")
    scale_estimates = relationship("ScaleEstimate", back_populates="foot_measurement")

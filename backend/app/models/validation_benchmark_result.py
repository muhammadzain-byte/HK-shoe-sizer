from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ValidationBenchmarkResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "validation_benchmark_results"
    __table_args__ = (
        Index("ix_validation_benchmark_results_validation_case_id", "validation_case_id"),
        Index("ix_validation_benchmark_results_scan_id", "scan_id"),
        Index("ix_validation_benchmark_results_failure_stage", "failure_stage"),
    )

    validation_case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("validation_cases.id"), nullable=False
    )
    scan_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("foot_scans.id"))
    measured_length_mm: Mapped[float | None] = mapped_column(Float)
    measured_width_mm: Mapped[float | None] = mapped_column(Float)
    ground_truth_length_mm: Mapped[float | None] = mapped_column(Float)
    ground_truth_width_mm: Mapped[float | None] = mapped_column(Float)
    length_error_mm: Mapped[float | None] = mapped_column(Float)
    width_error_mm: Mapped[float | None] = mapped_column(Float)
    length_abs_error_mm: Mapped[float | None] = mapped_column(Float)
    width_abs_error_mm: Mapped[float | None] = mapped_column(Float)
    length_error_percent: Mapped[float | None] = mapped_column(Float)
    width_error_percent: Mapped[float | None] = mapped_column(Float)
    capture_status: Mapped[str | None] = mapped_column(String(32))
    measurement_status: Mapped[str | None] = mapped_column(String(32))
    scale_status: Mapped[str | None] = mapped_column(String(32))
    size_status: Mapped[str | None] = mapped_column(String(64))
    recommended_size_system: Mapped[str | None] = mapped_column(String(32))
    recommended_size: Mapped[str | None] = mapped_column(String(32))
    failure_stage: Mapped[str | None] = mapped_column(String(64))
    failure_reasons_json: Mapped[list[str] | None] = mapped_column(JSON)
    pipeline_output_json: Mapped[dict | None] = mapped_column(JSON)

    validation_case = relationship("ValidationCase", back_populates="benchmark_results")
    scan = relationship("FootScan", back_populates="validation_benchmark_results")

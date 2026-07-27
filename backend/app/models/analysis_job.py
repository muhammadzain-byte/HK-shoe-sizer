from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        Index("ix_analysis_jobs_user_id", "user_id"),
        Index("ix_analysis_jobs_scan_id", "scan_id"),
        Index("ix_analysis_jobs_status", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    scan_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("foot_scans.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), default="measurement", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)

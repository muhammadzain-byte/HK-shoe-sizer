from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.user import User
from app.services.ai_processing_service import AIProcessingService
from app.services.scan_service import FootScanService


class AnalysisJobService:
    """Persistent status wrapper for expensive inference; callers poll instead of blocking."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, scan_id: UUID) -> AnalysisJob:
        FootScanService(self.db).get_scan(user, scan_id)
        active = self.db.scalar(
            select(AnalysisJob).where(
                AnalysisJob.user_id == user.id,
                AnalysisJob.scan_id == scan_id,
                AnalysisJob.status.in_(("queued", "running")),
            )
        )
        if active:
            return active
        job = AnalysisJob(user_id=user.id, scan_id=scan_id)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, user: User, job_id: UUID) -> AnalysisJob:
        job = self.db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id))
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found.")
        return job

    @staticmethod
    def run(job_id: UUID) -> None:
        db = SessionLocal()
        try:
            job = db.get(AnalysisJob, job_id)
            if not job or job.status != "queued":
                return
            job.status, job.progress, job.error = "running", 10, None
            db.commit()
            user = db.get(User, job.user_id)
            if not user:
                raise ValueError("Job owner no longer exists.")
            validation = AIProcessingService(db).process_scan(user, job.scan_id)
            if not validation.valid:
                job.status, job.progress = "failed", 100
                job.error = "; ".join(validation.issues)
                db.commit()
                return
            job.progress = 45
            db.commit()
            measurement = AIProcessingService(db).measure_scan(user, job.scan_id)
            job.status, job.progress = "completed", 100
            job.result = measurement.to_dict()
            db.commit()
        except Exception as exc:
            job = db.get(AnalysisJob, job_id)
            if job:
                job.status, job.progress, job.error = "failed", 100, str(exc)
                db.commit()
        finally:
            db.close()

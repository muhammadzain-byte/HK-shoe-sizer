from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.foot_scan import FootScan
from app.models.shoe_recommendation import ShoeRecommendation
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.schemas.scan import FootScanCreate, FootScanUpdate, PaginatedScanHistory, ScanDetailRead, ScanHistoryItem


class FootScanService:
    def __init__(self, db: Session):
        self.db = db

    def create_scan(self, user: User, payload: FootScanCreate) -> FootScan:
        scan = FootScan(user_id=user.id, foot_side=payload.foot_side, status="created")
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        return scan

    def list_scans(self, user: User, limit: int = 25, offset: int = 0) -> list[FootScan]:
        return list(
            self.db.scalars(
                select(FootScan)
                .where(FootScan.user_id == user.id)
                .order_by(FootScan.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )

    def get_scan(self, user: User, scan_id: UUID) -> FootScan:
        scan = self.db.scalar(
            select(FootScan).where(FootScan.id == scan_id, FootScan.user_id == user.id)
        )
        if not scan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
        return scan

    def update_scan(self, user: User, scan_id: UUID, payload: FootScanUpdate) -> FootScan:
        scan = self.get_scan(user, scan_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(scan, field, value)
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        return scan

    def detail(self, user: User, scan_id: UUID) -> ScanDetailRead:
        scan = self.get_scan(user, scan_id)
        uploaded_images = list(
            self.db.scalars(
                select(UploadedImage)
                .where(UploadedImage.foot_scan_id == scan.id, UploadedImage.user_id == user.id)
                .order_by(UploadedImage.created_at.desc())
            )
        )
        recommendation_count = self.db.scalar(
            select(func.count())
            .select_from(ShoeRecommendation)
            .where(ShoeRecommendation.foot_scan_id == scan.id)
        )
        return ScanDetailRead(
            **scan.__dict__,
            uploaded_images=uploaded_images,
            recommendation_count=recommendation_count or 0,
        )

    def history(self, user: User, limit: int, offset: int) -> PaginatedScanHistory:
        scans = self.list_scans(user, limit=limit, offset=offset)
        total = self.db.scalar(
            select(func.count()).select_from(FootScan).where(FootScan.user_id == user.id)
        )
        items = [
            ScanHistoryItem(
                scan=scan,
                recommendation_count=len(
                    self.db.scalars(
                        select(ShoeRecommendation).where(ShoeRecommendation.foot_scan_id == scan.id)
                    ).all()
                ),
                uploaded_image_count=len(
                    self.db.scalars(
                        select(UploadedImage).where(UploadedImage.foot_scan_id == scan.id)
                    ).all()
                ),
            )
            for scan in scans
        ]
        return PaginatedScanHistory(items=items, total=total or 0, limit=limit, offset=offset)

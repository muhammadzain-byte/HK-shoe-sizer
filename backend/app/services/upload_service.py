from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.foot_scan import FootScan
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.schemas.upload import CompleteUploadRequest, PresignUploadRequest, PresignUploadResponse
from app.services.storage.s3_service import S3StorageService


class UploadService:
    def __init__(self, db: Session, storage: S3StorageService | None = None):
        self.db = db
        self.storage = storage or S3StorageService()

    def presign_upload(self, user: User, payload: PresignUploadRequest) -> PresignUploadResponse:
        if payload.foot_scan_id:
            scan = self.db.scalar(
                select(FootScan).where(FootScan.id == payload.foot_scan_id, FootScan.user_id == user.id)
            )
            if not scan:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

        extension = PurePosixPath(payload.file_name).suffix.lower() or ".jpg"
        scan_segment = f"scans/{payload.foot_scan_id}" if payload.foot_scan_id else "uploads"
        object_key = f"users/{user.id}/{scan_segment}/{uuid4()}{extension}"
        upload = UploadedImage(
            user_id=user.id,
            foot_scan_id=payload.foot_scan_id,
            bucket=settings.aws_s3_bucket,
            object_key=object_key,
            content_type=payload.content_type,
            byte_size=payload.byte_size,
            upload_status="pending",
        )
        self.db.add(upload)
        self.db.commit()
        self.db.refresh(upload)

        presigned = self.storage.create_presigned_put_url(object_key, payload.content_type)
        return PresignUploadResponse(
            image_id=upload.id,
            upload_url=presigned.upload_url,
            headers=presigned.headers,
            object_key=object_key,
            expires_in_seconds=presigned.expires_in_seconds,
        )

    def complete_upload(self, user: User, payload: CompleteUploadRequest) -> UploadedImage:
        image = self.db.scalar(
            select(UploadedImage).where(
                UploadedImage.id == payload.image_id,
                UploadedImage.user_id == user.id,
            )
        )
        if not image:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

        if payload.foot_scan_id:
            scan = self.db.scalar(
                select(FootScan).where(FootScan.id == payload.foot_scan_id, FootScan.user_id == user.id)
            )
            if not scan:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
            image.foot_scan_id = scan.id
            if scan.status in {"created", "processing"}:
                scan.status = "image_uploaded"
            self.db.add(scan)

        image.checksum_sha256 = payload.checksum_sha256
        image.upload_status = "uploaded"
        self.db.add(image)
        self.db.commit()
        self.db.refresh(image)
        return image

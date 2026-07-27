from uuid import UUID
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.foot_scan import FootScan
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.models.validation_case import ValidationCase
from app.schemas.upload import (
    CompleteUploadRequest,
    LocalUploadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    UploadedImageRead,
)
from app.services.upload_service import UploadService


router = APIRouter()


@router.post("/local", response_model=LocalUploadResponse, status_code=status.HTTP_201_CREATED)
async def local_upload(
    file: UploadFile = File(...),
    foot_scan_id: UUID | None = Form(default=None),
    validation_case_id: UUID | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocalUploadResponse:
    if settings.storage_backend != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local upload is only available when STORAGE_BACKEND=local.",
        )
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload an image file.")

    extension = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
    scan: FootScan | None = None
    if foot_scan_id:
        scan = db.scalar(
            select(FootScan).where(
                FootScan.id == foot_scan_id,
                FootScan.user_id == current_user.id,
            )
        )
        if not scan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

    storage_dir = Path(settings.local_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{extension}"
    storage_path = storage_dir / filename
    data = await file.read()
    storage_path.write_bytes(data)

    image = UploadedImage(
        user_id=current_user.id,
        foot_scan_id=foot_scan_id,
        bucket="local",
        object_key=filename,
        content_type=file.content_type,
        byte_size=len(data),
        upload_status="uploaded",
    )
    db.add(image)
    db.flush()
    if scan:
        scan.status = "image_uploaded"
        db.add(scan)

    if validation_case_id:
        validation_case = db.scalar(
            select(ValidationCase).where(
                ValidationCase.id == validation_case_id,
                ValidationCase.user_id == current_user.id,
            )
        )
        if not validation_case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation case not found.")
        validation_case.image_upload_id = image.id
        if foot_scan_id:
            validation_case.scan_id = foot_scan_id
        validation_case.status = "image_uploaded" if validation_case.status == "draft" else validation_case.status
        db.add(validation_case)

    db.commit()
    db.refresh(image)
    file_url = f"{settings.public_upload_base_url.rstrip('/')}/{filename}"
    return LocalUploadResponse(
        image_id=image.id,
        file_url=file_url,
        storage_path=str(storage_path),
        mime_type=file.content_type,
        size_bytes=len(data),
    )


@router.post("/presign", response_model=PresignUploadResponse)
def presign_upload(
    payload: PresignUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresignUploadResponse:
    return UploadService(db).presign_upload(current_user, payload)


@router.post("/complete", response_model=UploadedImageRead)
def complete_upload(
    payload: CompleteUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadedImage:
    return UploadService(db).complete_upload(current_user, payload)


@router.get("/{image_id}", response_model=UploadedImageRead)
def read_upload(
    image_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadedImage:
    image = db.scalar(
        select(UploadedImage).where(
            UploadedImage.id == image_id,
            UploadedImage.user_id == current_user.id,
        )
    )
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    return image

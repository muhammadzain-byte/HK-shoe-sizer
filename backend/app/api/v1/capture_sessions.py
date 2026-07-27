from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.capture_session import (
    CaptureSessionAttachRequest,
    CaptureSessionCreate,
    CaptureSessionListResponse,
    CaptureSessionRead,
)
from app.services.capture_metadata_service import CaptureMetadataService


router = APIRouter()


@router.post("", response_model=CaptureSessionRead, status_code=status.HTTP_201_CREATED)
def create_capture_session(
    payload: CaptureSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaptureSessionRead:
    service = CaptureMetadataService(db)
    session = service.create_capture_session(
        current_user,
        capture_quality=payload.capture_quality,
        device_metadata=payload.device_metadata,
        foot_scan_id=payload.foot_scan_id,
        uploaded_image_id=payload.uploaded_image_id,
    )
    return service.to_read(session)


@router.get("", response_model=CaptureSessionListResponse)
def list_capture_sessions(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaptureSessionListResponse:
    service = CaptureMetadataService(db)
    sessions, total = service.list_user_capture_sessions(current_user, limit=limit, offset=offset)
    return CaptureSessionListResponse(
        items=[service.to_read(session) for session in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{capture_session_id}", response_model=CaptureSessionRead)
def read_capture_session(
    capture_session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaptureSessionRead:
    service = CaptureMetadataService(db)
    return service.to_read(service.get_capture_session(current_user, capture_session_id))


@router.patch("/{capture_session_id}/attach", response_model=CaptureSessionRead)
def attach_capture_session(
    capture_session_id: UUID,
    payload: CaptureSessionAttachRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaptureSessionRead:
    service = CaptureMetadataService(db)
    session = service.attach(
        current_user,
        capture_session_id,
        foot_scan_id=payload.foot_scan_id,
        uploaded_image_id=payload.uploaded_image_id,
    )
    return service.to_read(session)

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.foot_scan import FootScan
from app.models.user import User
from app.schemas.capture_session import CaptureSessionListResponse
from app.schemas.scan import (
    FootScanCreate,
    FootScanRead,
    FootScanUpdate,
    PaginatedScanHistory,
    ScanDetailRead,
)
from app.services.capture_metadata_service import CaptureMetadataService
from app.services.scan_service import FootScanService


router = APIRouter()


@router.post("", response_model=FootScanRead, status_code=status.HTTP_201_CREATED)
def create_scan(
    payload: FootScanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FootScan:
    return FootScanService(db).create_scan(current_user, payload)


@router.get("", response_model=list[FootScanRead])
def list_scans(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FootScan]:
    return FootScanService(db).list_scans(current_user, limit=limit, offset=offset)


@router.get("/history", response_model=PaginatedScanHistory)
def scan_history(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedScanHistory:
    return FootScanService(db).history(current_user, limit=limit, offset=offset)


@router.get("/{scan_id}", response_model=ScanDetailRead)
def read_scan(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanDetailRead:
    return FootScanService(db).detail(current_user, scan_id)


@router.get("/{scan_id}/capture-sessions", response_model=CaptureSessionListResponse)
def list_scan_capture_sessions(
    scan_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaptureSessionListResponse:
    service = CaptureMetadataService(db)
    sessions, total = service.list_scan_capture_sessions(current_user, scan_id, limit=limit, offset=offset)
    return CaptureSessionListResponse(
        items=[service.to_read(session) for session in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{scan_id}", response_model=FootScanRead)
def update_scan(
    scan_id: UUID,
    payload: FootScanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FootScan:
    return FootScanService(db).update_scan(current_user, scan_id, payload)


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_scan(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    scan = FootScanService(db).get_scan(current_user, scan_id)
    scan.status = "archived"
    db.add(scan)
    db.commit()
    return None

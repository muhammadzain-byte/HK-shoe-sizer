from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.validation_case import (
    ValidationBenchmarkResultRead,
    ValidationCaseAttachUpload,
    ValidationCaseCreate,
    ValidationCaseLinkScan,
    ValidationCaseListResponse,
    ValidationCaseRead,
    ValidationCaseSummary,
    ValidationCaseUpdate,
)
from app.services.validation_benchmark_service import ValidationBenchmarkService
from app.services.validation_case_service import ValidationCaseService


router = APIRouter()


@router.post("", response_model=ValidationCaseRead, status_code=status.HTTP_201_CREATED)
def create_validation_case(
    payload: ValidationCaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseRead:
    return ValidationCaseService(db).create_case(current_user, payload)


@router.get("/summary", response_model=ValidationCaseSummary)
def validation_case_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseSummary:
    return ValidationCaseService(db).summary(current_user)


@router.get("", response_model=ValidationCaseListResponse)
def list_validation_cases(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseListResponse:
    cases, total = ValidationCaseService(db).list_cases(
        current_user,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )
    return ValidationCaseListResponse(items=cases, total=total, limit=limit, offset=offset)


@router.get("/{validation_case_id}", response_model=ValidationCaseRead)
def read_validation_case(
    validation_case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseRead:
    return ValidationCaseService(db).get_case(current_user, validation_case_id)


@router.patch("/{validation_case_id}", response_model=ValidationCaseRead)
def update_validation_case(
    validation_case_id: UUID,
    payload: ValidationCaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseRead:
    return ValidationCaseService(db).update_case(current_user, validation_case_id, payload)


@router.delete("/{validation_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_validation_case(
    validation_case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    ValidationCaseService(db).delete_case(current_user, validation_case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{validation_case_id}/attach-upload", response_model=ValidationCaseRead)
def attach_upload(
    validation_case_id: UUID,
    payload: ValidationCaseAttachUpload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseRead:
    return ValidationCaseService(db).attach_upload(current_user, validation_case_id, payload.image_upload_id)


@router.post("/{validation_case_id}/link-scan", response_model=ValidationCaseRead)
def link_scan(
    validation_case_id: UUID,
    payload: ValidationCaseLinkScan,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseRead:
    return ValidationCaseService(db).link_scan(
        current_user,
        validation_case_id,
        payload.scan_id,
        capture_session_id=payload.capture_session_id,
    )


@router.post("/{validation_case_id}/mark-benchmark-ready", response_model=ValidationCaseRead)
def mark_benchmark_ready(
    validation_case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCaseRead:
    return ValidationCaseService(db).mark_benchmark_ready(current_user, validation_case_id)


@router.post("/{validation_case_id}/run-benchmark", response_model=ValidationBenchmarkResultRead)
def run_benchmark(
    validation_case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationBenchmarkResultRead:
    return ValidationBenchmarkService(db).run_case_benchmark(current_user, validation_case_id)

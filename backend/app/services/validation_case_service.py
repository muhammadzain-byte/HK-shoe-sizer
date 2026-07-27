from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.capture_session import CaptureSession
from app.models.foot_scan import FootScan
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.models.validation_case import ValidationCase
from app.schemas.validation_case import ValidationCaseCreate, ValidationCaseUpdate


VALIDATION_STATUSES = {
    "draft",
    "image_uploaded",
    "annotated",
    "scan_linked",
    "benchmark_ready",
    "benchmark_completed",
    "rejected",
}


class ValidationCaseService:
    def __init__(self, db: Session):
        self.db = db

    def create_case(self, user: User, payload: ValidationCaseCreate) -> ValidationCase:
        self._validate_payload(payload.model_dump(exclude_unset=True), require_reference=False)
        case = ValidationCase(user_id=user.id, **payload.model_dump())
        case.status = self._derive_status(case)
        self._check_linked_resources(user, case)
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def get_case(self, user: User, validation_case_id: UUID) -> ValidationCase:
        case = self.db.scalar(
            select(ValidationCase).where(
                ValidationCase.id == validation_case_id,
                ValidationCase.user_id == user.id,
            )
        )
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation case not found.")
        return case

    def list_cases(
        self,
        user: User,
        *,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ) -> tuple[list[ValidationCase], int]:
        statement = select(ValidationCase).where(ValidationCase.user_id == user.id)
        count_statement = select(func.count()).select_from(ValidationCase).where(ValidationCase.user_id == user.id)
        if status_filter:
            statement = statement.where(ValidationCase.status == status_filter)
            count_statement = count_statement.where(ValidationCase.status == status_filter)
        total = self.db.scalar(count_statement) or 0
        cases = list(self.db.scalars(statement.order_by(ValidationCase.created_at.desc()).limit(limit).offset(offset)))
        return cases, total

    def update_case(
        self,
        user: User,
        validation_case_id: UUID,
        payload: ValidationCaseUpdate,
    ) -> ValidationCase:
        case = self.get_case(user, validation_case_id)
        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates and updates["status"] not in VALIDATION_STATUSES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid validation status.")
        self._validate_payload(updates, require_reference=False)
        for key, value in updates.items():
            setattr(case, key, value)
        self._check_linked_resources(user, case)
        if "status" not in updates:
            case.status = self._derive_status(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def delete_case(self, user: User, validation_case_id: UUID) -> None:
        case = self.get_case(user, validation_case_id)
        self.db.delete(case)
        self.db.commit()

    def attach_upload(self, user: User, validation_case_id: UUID, image_upload_id: UUID) -> ValidationCase:
        case = self.get_case(user, validation_case_id)
        image = self._get_owned_upload(user, image_upload_id)
        case.image_upload_id = image.id
        if image.foot_scan_id and not case.scan_id:
            case.scan_id = image.foot_scan_id
        case.status = self._derive_status(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def link_scan(
        self,
        user: User,
        validation_case_id: UUID,
        scan_id: UUID,
        capture_session_id: UUID | None = None,
    ) -> ValidationCase:
        case = self.get_case(user, validation_case_id)
        scan = self._get_owned_scan(user, scan_id)
        case.scan_id = scan.id
        if capture_session_id:
            case.capture_session_id = self._get_owned_capture_session(user, capture_session_id).id
        case.status = self._derive_status(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def mark_benchmark_ready(self, user: User, validation_case_id: UUID) -> ValidationCase:
        case = self.get_case(user, validation_case_id)
        issues = self.benchmark_readiness_issues(case)
        if issues:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Validation case is not benchmark-ready.", "issues": issues},
            )
        case.status = "benchmark_ready"
        self.db.commit()
        self.db.refresh(case)
        return case

    def benchmark_readiness_issues(self, case: ValidationCase) -> list[str]:
        issues: list[str] = []
        if not case.image_upload_id:
            issues.append("A real uploaded image is required.")
        if not case.ground_truth_length_mm or not case.ground_truth_width_mm:
            issues.append("Manual ground-truth length and width in millimeters are required.")
        if not case.scan_id:
            issues.append("A linked scan is required before benchmark execution.")
        if case.reference_mode != "none" and not self._has_reference_evidence(case):
            issues.append("Reference object dimensions and bbox/polygon are required.")
        if case.reference_mode == "none":
            issues.append("A reference object or calibration evidence is required for real-world benchmark.")
        return issues

    def summary(self, user: User) -> dict:
        cases = list(self.db.scalars(select(ValidationCase).where(ValidationCase.user_id == user.id)))
        return {
            "total": len(cases),
            "by_status": self._count_by(cases, "status"),
            "by_device_os": self._count_by(cases, "device_os"),
            "by_capture_scenario": self._count_by(cases, "capture_scenario"),
            "benchmark_ready_count": sum(1 for case in cases if case.status == "benchmark_ready"),
            "benchmark_completed_count": sum(1 for case in cases if case.status == "benchmark_completed"),
        }

    def _derive_status(self, case: ValidationCase) -> str:
        if case.status == "rejected":
            return "rejected"
        if case.scan_id:
            return "scan_linked"
        if self._has_reference_evidence(case) and case.ground_truth_length_mm and case.ground_truth_width_mm:
            return "annotated"
        if case.image_upload_id:
            return "image_uploaded"
        return "draft"

    def _validate_payload(self, payload: dict, *, require_reference: bool) -> None:
        if payload.get("ground_truth_length_mm") is not None and payload["ground_truth_length_mm"] <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Foot length must be positive.")
        if payload.get("ground_truth_width_mm") is not None and payload["ground_truth_width_mm"] <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Foot width must be positive.")
        reference_mode = payload.get("reference_mode")
        if reference_mode and reference_mode not in {"none", "credit_card", "a4_paper", "calibration_card", "custom_object"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported reference mode.")
        if require_reference and reference_mode != "none":
            required = ["reference_width_mm", "reference_height_mm"]
            missing = [key for key in required if not payload.get(key)]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing reference fields: {', '.join(missing)}",
                )

    def _has_reference_evidence(self, case: ValidationCase) -> bool:
        dimensions = bool(case.reference_width_mm and case.reference_height_mm)
        bbox = all(
            value is not None and value > 0
            for value in (
                case.reference_bbox_width,
                case.reference_bbox_height,
            )
        ) and case.reference_bbox_x is not None and case.reference_bbox_y is not None
        polygon = bool(case.reference_polygon_json)
        return dimensions and (bbox or polygon)

    def _check_linked_resources(self, user: User, case: ValidationCase) -> None:
        if case.image_upload_id:
            self._get_owned_upload(user, case.image_upload_id)
        if case.scan_id:
            self._get_owned_scan(user, case.scan_id)
        if case.capture_session_id:
            self._get_owned_capture_session(user, case.capture_session_id)

    def _get_owned_upload(self, user: User, image_upload_id: UUID) -> UploadedImage:
        image = self.db.scalar(
            select(UploadedImage).where(UploadedImage.id == image_upload_id, UploadedImage.user_id == user.id)
        )
        if not image:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded image not found.")
        return image

    def _get_owned_scan(self, user: User, scan_id: UUID) -> FootScan:
        scan = self.db.scalar(select(FootScan).where(FootScan.id == scan_id, FootScan.user_id == user.id))
        if not scan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foot scan not found.")
        return scan

    def _get_owned_capture_session(self, user: User, capture_session_id: UUID) -> CaptureSession:
        capture_session = self.db.scalar(
            select(CaptureSession).where(CaptureSession.id == capture_session_id, CaptureSession.user_id == user.id)
        )
        if not capture_session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture session not found.")
        return capture_session

    def _count_by(self, cases: list[ValidationCase], attribute: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in cases:
            value = getattr(case, attribute) or "unknown"
            counts[value] = counts.get(value, 0) + 1
        return counts

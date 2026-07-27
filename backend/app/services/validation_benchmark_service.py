from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.capture_session import CaptureSession
from app.models.foot_measurement import FootMeasurement
from app.models.scale_estimate import ScaleEstimate
from app.models.shoe_recommendation import ShoeRecommendation
from app.models.user import User
from app.models.validation_benchmark_result import ValidationBenchmarkResult
from app.models.validation_case import ValidationCase
from app.schemas.pipeline import FullPipelineRequest
from app.schemas.scale import ReferenceObjectInput
from app.services.scan_orchestration_service import ScanOrchestrationService
from app.services.validation_case_service import ValidationCaseService


class ValidationBenchmarkService:
    def __init__(self, db: Session):
        self.db = db

    def run_case_benchmark(self, user: User, validation_case_id: UUID) -> ValidationBenchmarkResult:
        case = ValidationCaseService(self.db).get_case(user, validation_case_id)
        readiness_issues = ValidationCaseService(self.db).benchmark_readiness_issues(case)
        if readiness_issues:
            result = self._persist_failure(case, "readiness", readiness_issues)
            return result

        orchestration_output = self._try_run_safe_pipeline(user, case)
        measurement = self._latest_measurement(case.scan_id)
        scale = self._latest_scale_estimate(user, case.scan_id)
        capture = self._latest_capture_session(user, case)
        shoe = self._latest_shoe_recommendation(user, case.scan_id)

        failure_stage, failure_reasons = self._failure_status(case, capture, measurement, scale)
        measured_length = scale.foot_length_mm if scale else None
        measured_width = scale.foot_width_mm if scale else None
        length_error = self._error(measured_length, case.ground_truth_length_mm)
        width_error = self._error(measured_width, case.ground_truth_width_mm)

        result = ValidationBenchmarkResult(
            validation_case_id=case.id,
            scan_id=case.scan_id,
            measured_length_mm=measured_length,
            measured_width_mm=measured_width,
            ground_truth_length_mm=case.ground_truth_length_mm,
            ground_truth_width_mm=case.ground_truth_width_mm,
            length_error_mm=length_error,
            width_error_mm=width_error,
            length_abs_error_mm=abs(length_error) if length_error is not None else None,
            width_abs_error_mm=abs(width_error) if width_error is not None else None,
            length_error_percent=self._error_percent(length_error, case.ground_truth_length_mm),
            width_error_percent=self._error_percent(width_error, case.ground_truth_width_mm),
            capture_status=capture.capture_status if capture else "missing",
            measurement_status=measurement.measurement_status if measurement else "missing",
            scale_status=scale.scale_status if scale else "unavailable",
            size_status=shoe.recommendation_status if shoe else "not_run",
            recommended_size_system=shoe.size_system if shoe else None,
            recommended_size=shoe.recommended_size if shoe else None,
            failure_stage=failure_stage,
            failure_reasons_json=failure_reasons,
            pipeline_output_json={
                "validation_case_id": str(case.id),
                "scan_id": str(case.scan_id) if case.scan_id else None,
                "reference_mode": case.reference_mode,
                "device_group": f"{case.device_os or 'unknown'}:{case.browser or 'unknown'}",
                "orchestration": orchestration_output,
                "safety_note": "Real accuracy requires real-device images and manual millimeter ground truth.",
            },
        )
        self.db.add(result)
        case.status = "benchmark_completed"
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_result(self, user: User, result_id: UUID) -> ValidationBenchmarkResult:
        result = self.db.scalar(
            select(ValidationBenchmarkResult)
            .join(ValidationCase)
            .where(
                ValidationBenchmarkResult.id == result_id,
                ValidationCase.user_id == user.id,
            )
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark result not found.")
        return result

    def _persist_failure(
        self,
        case: ValidationCase,
        failure_stage: str,
        reasons: list[str],
    ) -> ValidationBenchmarkResult:
        result = ValidationBenchmarkResult(
            validation_case_id=case.id,
            scan_id=case.scan_id,
            ground_truth_length_mm=case.ground_truth_length_mm,
            ground_truth_width_mm=case.ground_truth_width_mm,
            capture_status="missing",
            measurement_status="missing",
            scale_status="unavailable",
            size_status="blocked",
            failure_stage=failure_stage,
            failure_reasons_json=reasons,
            pipeline_output_json={"safety_note": "Benchmark did not run because required evidence is missing."},
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def _failure_status(
        self,
        case: ValidationCase,
        capture: CaptureSession | None,
        measurement: FootMeasurement | None,
        scale: ScaleEstimate | None,
    ) -> tuple[str | None, list[str]]:
        if capture and capture.capture_status == "reject":
            return "capture", ["Capture quality was rejected."]
        if not measurement:
            return "measurement", ["No pixel measurement exists for the linked scan."]
        if measurement.measurement_status != "trusted":
            return "measurement", [f"Measurement status is {measurement.measurement_status}, not trusted."]
        if not scale:
            return "scale", ["No scale estimate exists for the linked scan."]
        if scale.scale_status != "available" or scale.confidence < 0.85:
            return "scale", ["Scale is unavailable or below confidence threshold."]
        if scale.foot_length_mm is None or scale.foot_width_mm is None:
            return "scale", ["Real-world length/width are missing."]
        if not case.ground_truth_length_mm or not case.ground_truth_width_mm:
            return "ground_truth", ["Manual ground truth is missing."]
        return None, []

    def _latest_measurement(self, scan_id: UUID | None) -> FootMeasurement | None:
        if not scan_id:
            return None
        return self.db.scalar(
            select(FootMeasurement).where(FootMeasurement.scan_id == scan_id).order_by(FootMeasurement.created_at.desc())
        )

    def _latest_scale_estimate(self, user: User, scan_id: UUID | None) -> ScaleEstimate | None:
        if not scan_id:
            return None
        return self.db.scalar(
            select(ScaleEstimate)
            .where(ScaleEstimate.user_id == user.id, ScaleEstimate.foot_scan_id == scan_id)
            .order_by(ScaleEstimate.created_at.desc())
        )

    def _latest_capture_session(self, user: User, case: ValidationCase) -> CaptureSession | None:
        if case.capture_session_id:
            return self.db.scalar(
                select(CaptureSession).where(
                    CaptureSession.id == case.capture_session_id,
                    CaptureSession.user_id == user.id,
                )
            )
        if not case.scan_id:
            return None
        return self.db.scalar(
            select(CaptureSession)
            .where(CaptureSession.user_id == user.id, CaptureSession.foot_scan_id == case.scan_id)
            .order_by(CaptureSession.created_at.desc())
        )

    def _latest_shoe_recommendation(self, user: User, scan_id: UUID | None) -> ShoeRecommendation | None:
        if not scan_id:
            return None
        return self.db.scalar(
            select(ShoeRecommendation)
            .where(ShoeRecommendation.user_id == user.id, ShoeRecommendation.foot_scan_id == scan_id)
            .order_by(ShoeRecommendation.created_at.desc())
        )

    def _try_run_safe_pipeline(self, user: User, case: ValidationCase) -> dict:
        if not case.scan_id:
            return {"attempted": False, "reason": "No linked scan."}
        reference_object = self._reference_object_from_case(case)
        if not reference_object:
            return {"attempted": False, "reason": "No valid reference object."}
        try:
            result = ScanOrchestrationService(self.db).run_full_pipeline(
                user,
                case.scan_id,
                FullPipelineRequest(reference_object=reference_object, run_shoe_size=True),
            )
        except Exception as exc:
            return {"attempted": True, "failed": True, "reason": str(exc)}
        return {
            "attempted": True,
            "overall_status": result.overall_status,
            "next_action": result.next_action,
            "user_message": result.user_message,
        }

    def _reference_object_from_case(self, case: ValidationCase) -> ReferenceObjectInput | None:
        if case.reference_mode not in {"credit_card", "a4_paper", "calibration_card", "custom_object"}:
            return None
        if not (
            case.reference_width_mm
            and case.reference_height_mm
            and case.reference_bbox_x is not None
            and case.reference_bbox_y is not None
            and case.reference_bbox_width
            and case.reference_bbox_height
        ):
            return None
        return ReferenceObjectInput(
            type=case.reference_mode,
            reference_mode=case.reference_mode,
            known_width_mm=case.reference_width_mm,
            known_height_mm=case.reference_height_mm,
            bbox={
                "x": case.reference_bbox_x,
                "y": case.reference_bbox_y,
                "width": case.reference_bbox_width,
                "height": case.reference_bbox_height,
            },
            polygon=case.reference_polygon_json,
            detection_confidence=0.95,
            same_plane_confidence=0.90,
            distortion_score=0.10,
            source="manual",
        )

    def _error(self, measured: float | None, ground_truth: float | None) -> float | None:
        if measured is None or ground_truth is None:
            return None
        return round(measured - ground_truth, 3)

    def _error_percent(self, error: float | None, ground_truth: float | None) -> float | None:
        if error is None or not ground_truth:
            return None
        return round(error / ground_truth * 100, 3)

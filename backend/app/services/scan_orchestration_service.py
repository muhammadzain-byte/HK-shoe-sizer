from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.capture_session import CaptureSession
from app.models.foot_measurement import FootMeasurement
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.schemas.pipeline import FullPipelineRequest, FullPipelineResponse, PipelineStageResult
from app.schemas.shoe_size import ShoeSizeRequest
from app.services.ai_processing_service import AIProcessingService
from app.services.reference_object_detection_service import ReferenceObjectDetectionResult, ReferenceObjectDetectionService
from app.services.scan_service import FootScanService
from app.services.scale_estimate_persistence_service import ScaleEstimatePersistenceService
from app.services.scale_estimation_service import ScaleEstimateResult, ScaleEstimationService
from app.services.shoe_recommendation_persistence_service import ShoeRecommendationPersistenceService
from app.services.shoe_size_service import ShoeSizeService
from app.services.storage.s3_service import S3StorageService


class ScanOrchestrationService:
    def __init__(self, db: Session):
        self.db = db

    def run_full_pipeline(
        self,
        user: User,
        scan_id: UUID,
        payload: FullPipelineRequest,
    ) -> FullPipelineResponse:
        scan = FootScanService(self.db).get_scan(user, scan_id)
        image = self._latest_uploaded_image(user, scan.id)
        if not image:
            return self._response(
                overall_status="failed",
                capture_quality=self._stage("failed", issues=["No uploaded image is attached to this scan."]),
                measurement=self._stage("not_run"),
                landmark_validation=self._stage("not_run"),
                scale_estimate=self._stage("not_run"),
                next_action="Upload a guided capture before running analysis.",
                user_message="No uploaded image is attached to this scan.",
            )

        capture_session = self._latest_capture_session(user, scan.id)
        capture_stage = self._capture_stage(capture_session)
        if capture_stage.stage_status != "passed":
            return self._response(
                overall_status="capture_needs_adjustment",
                capture_quality=capture_stage,
                measurement=self._stage("not_run"),
                landmark_validation=self._stage("not_run"),
                scale_estimate=self._stage("not_run"),
                next_action=self._capture_next_action(capture_session),
                user_message="Capture quality must pass before measurement and sizing.",
            )

        measurement = self._latest_measurement(scan.id)
        if not measurement:
            try:
                AIProcessingService(self.db).measure_scan(user, scan.id)
                measurement = self._latest_measurement(scan.id)
            except Exception as exc:
                return self._response(
                    overall_status="failed",
                    capture_quality=capture_stage,
                    measurement=self._stage("failed", issues=[str(exc)]),
                    landmark_validation=self._stage("not_run"),
                    scale_estimate=self._stage("not_run"),
                    next_action="Run measurement again after checking the uploaded image.",
                    user_message="Measurement could not be completed.",
                )

        measurement_payload = self._measurement_payload(measurement)
        measurement_stage = self._measurement_stage(measurement_payload)
        landmark_stage = self._landmark_stage(measurement_payload)
        if measurement_stage.stage_status != "passed":
            return self._response(
                overall_status="measurement_needs_review",
                capture_quality=capture_stage,
                measurement=measurement_stage,
                landmark_validation=landmark_stage,
                scale_estimate=self._stage("not_run"),
                next_action="Review or rerun anatomical landmark validation.",
                user_message="Measurement is not trusted yet, so scale and size are blocked.",
            )

        reference_object = payload.reference_object
        reference_detection: ReferenceObjectDetectionResult | None = None
        if payload.reference_object_detection and payload.reference_object_detection.enabled:
            reference_detection = self._detect_reference_object(image, payload.reference_object_detection)
            if reference_detection.detected:
                reference_object = reference_detection.reference_object

        scale_result = (
            self._needs_reference_scale_result(reference_detection)
            if reference_detection is not None and not reference_detection.detected
            else ScaleEstimationService().estimate_scale(
                measurement=measurement_payload,
                capture_session=capture_session,
                reference_object=reference_object,
                depth_metadata=payload.depth_metadata,
            )
        )
        scale_record = ScaleEstimatePersistenceService(self.db).persist_estimate(
            user,
            scan.id,
            scale_result,
            foot_measurement_id=measurement.id if measurement else None,
            capture_session_id=capture_session.id if capture_session else None,
        )
        scale_stage = PipelineStageResult(
            stage_status="passed" if scale_result.scale_status == "available" else "blocked",
            data=scale_result.to_dict(),
            issues=scale_result.issues,
        )
        if scale_result.scale_status != "available":
            return self._response(
                overall_status="scale_unavailable",
                capture_quality=capture_stage,
                measurement=measurement_stage,
                landmark_validation=landmark_stage,
                scale_estimate=scale_stage,
                next_action="Use a reference object or supported depth mode for real-world scale.",
                user_message="Scale is unavailable, so shoe size is blocked.",
                debug=self._debug_payload(scale_record.id, reference_detection),
            )

        if not payload.run_shoe_size:
            return self._response(
                overall_status="ready_for_size",
                capture_quality=capture_stage,
                measurement=measurement_stage,
                landmark_validation=landmark_stage,
                scale_estimate=scale_stage,
                next_action="Request shoe size recommendation when ready.",
                user_message="Measurement and scale are ready for women-only size recommendation.",
                debug=self._debug_payload(scale_record.id, reference_detection),
            )

        shoe_request = self._shoe_request(payload.shoe_size_request, measurement_payload, scale_result)
        shoe_response = ShoeSizeService().recommend_size(shoe_request)
        ShoeRecommendationPersistenceService(self.db).persist_recommendation(
            user,
            scan.id,
            shoe_request,
            shoe_response,
            scale_estimate_id=scale_record.id,
        )
        overall = "size_recommended" if shoe_response.recommendation_status == "recommended" else "ready_for_size"
        return self._response(
            overall_status=overall,
            capture_quality=capture_stage,
            measurement=measurement_stage,
            landmark_validation=landmark_stage,
            scale_estimate=scale_stage,
            shoe_recommendation=shoe_response,
            next_action=(
                "Use the recommended size as an advisory generic chart result."
                if overall == "size_recommended"
                else "Resolve the size recommendation blocker."
            ),
            user_message=(
                f"Recommended women's {shoe_response.size_system} size: {shoe_response.recommended_size}."
                if overall == "size_recommended"
                else shoe_response.blocked_reason or "Size recommendation is blocked."
            ),
            debug=self._debug_payload(scale_record.id, reference_detection),
        )

    def _latest_uploaded_image(self, user: User, scan_id: UUID) -> UploadedImage | None:
        return self.db.scalar(
            select(UploadedImage)
            .where(
                UploadedImage.user_id == user.id,
                UploadedImage.foot_scan_id == scan_id,
                UploadedImage.upload_status == "uploaded",
            )
            .order_by(UploadedImage.created_at.desc())
        )

    def _latest_capture_session(self, user: User, scan_id: UUID) -> CaptureSession | None:
        return self.db.scalar(
            select(CaptureSession)
            .where(CaptureSession.user_id == user.id, CaptureSession.foot_scan_id == scan_id)
            .order_by(CaptureSession.created_at.desc())
        )

    def _latest_measurement(self, scan_id: UUID) -> FootMeasurement | None:
        return self.db.scalar(
            select(FootMeasurement)
            .where(FootMeasurement.scan_id == scan_id)
            .order_by(FootMeasurement.created_at.desc())
        )

    def _capture_stage(self, capture_session: CaptureSession | None) -> PipelineStageResult:
        if not capture_session:
            return self._stage("blocked", issues=["Capture quality has not been stored for this scan."])
        status = capture_session.capture_status
        if status == "ready":
            return self._stage("passed", data={"capture_status": status, "score": capture_session.capture_quality_score})
        return self._stage(
            "failed" if status == "reject" else "blocked",
            data={"capture_status": status, "score": capture_session.capture_quality_score},
            issues=capture_session.issues or [],
        )

    def _measurement_stage(self, measurement: dict[str, Any]) -> PipelineStageResult:
        status = measurement.get("measurement_status")
        if status == "trusted":
            return self._stage("passed", data=measurement)
        if status in {"failed_quality_gate", "failed"}:
            return self._stage("failed", data=measurement, issues=["Measurement failed quality gate."])
        return self._stage("blocked", data=measurement, issues=["Measurement is not trusted."])

    def _landmark_stage(self, measurement: dict[str, Any]) -> PipelineStageResult:
        status = measurement.get("measurement_status")
        if status == "trusted":
            return self._stage("passed", data={"measurement_status": status})
        return self._stage("blocked", data={"measurement_status": status}, issues=["Landmarks require review."])

    def _measurement_payload(self, measurement: FootMeasurement | None) -> dict[str, Any]:
        if not measurement:
            return {"measurement_status": "missing"}
        return {
            "measurement_status": measurement.measurement_status,
            "foot_length_pixels": float(measurement.foot_length_pixels or 0),
            "foot_width_pixels": float(measurement.foot_width_pixels or 0),
        }

    def _shoe_request(
        self,
        request: ShoeSizeRequest | None,
        measurement: dict[str, Any],
        scale_result,
    ) -> ShoeSizeRequest:
        base = request or ShoeSizeRequest(
            region="EU",
            gender="women",
            fit_preference="regular",
            shoe_type="flat",
        )
        real_world = scale_result.real_world_measurement
        return ShoeSizeRequest(
            region=base.region,
            gender=base.gender,
            fit_preference=base.fit_preference,
            shoe_type=base.shoe_type,
            foot_length_mm=real_world.foot_length_mm if real_world else None,
            foot_width_mm=real_world.foot_width_mm if real_world else None,
            measurement_status=measurement.get("measurement_status", ""),
            scale_status=scale_result.scale_status,
            scale_confidence=scale_result.confidence,
            capture_status="ready",
        )

    def _detect_reference_object(self, image: UploadedImage, options) -> ReferenceObjectDetectionResult:
        payload = options.model_dump(mode="json") if hasattr(options, "model_dump") else dict(options)
        image_bytes = None
        if not payload.get("manual_bbox") and not payload.get("manual_polygon"):
            try:
                image_bytes = S3StorageService().get_object_bytes(image.bucket, image.object_key)
            except Exception:
                image_bytes = None
        return ReferenceObjectDetectionService().detect_reference_object(
            image_bytes=image_bytes,
            reference_mode=payload.get("reference_mode", "none"),
            known_width_mm=payload.get("known_width_mm"),
            known_height_mm=payload.get("known_height_mm"),
            manual_bbox=payload.get("manual_bbox"),
            manual_polygon=payload.get("manual_polygon"),
            detection_confidence=payload.get("detection_confidence"),
            same_plane_confidence=payload.get("same_plane_confidence"),
            distortion_score=payload.get("distortion_score"),
            source=payload.get("source", "manual"),
        )

    def _needs_reference_scale_result(
        self,
        detection: ReferenceObjectDetectionResult | None,
    ) -> ScaleEstimateResult:
        detection_payload = detection.to_dict() if detection else {}
        return ScaleEstimateResult(
            scale_status="needs_reference",
            scale_mode="reference_object",
            pixels_per_mm=None,
            mm_per_pixel=None,
            confidence=detection.confidence if detection else 0.0,
            evidence={"reference_detection": detection_payload},
            issues=(detection.issues if detection else ["Reference object was not detected."]),
            instructions=(
                detection.instructions
                if detection
                else ["Place the reference object fully visible beside your foot and retake."]
            ),
        )

    def _debug_payload(
        self,
        scale_estimate_id,
        reference_detection: ReferenceObjectDetectionResult | None,
    ) -> dict[str, Any]:
        debug = {"scale_estimate_id": str(scale_estimate_id)}
        if reference_detection:
            debug["reference_detection"] = reference_detection.to_dict()
        return debug

    def _capture_next_action(self, capture_session: CaptureSession | None) -> str:
        if not capture_session:
            return "Run capture quality before analysis."
        if capture_session.primary_instruction:
            return f"Retake photo: {capture_session.primary_instruction}"
        return "Retake photo with guided capture."

    def _stage(
        self,
        status: str,
        data: dict[str, Any] | None = None,
        issues: list[str] | None = None,
    ) -> PipelineStageResult:
        return PipelineStageResult(stage_status=status, data=data or {}, issues=issues or [])

    def _response(
        self,
        overall_status: str,
        capture_quality: PipelineStageResult,
        measurement: PipelineStageResult,
        landmark_validation: PipelineStageResult,
        scale_estimate: PipelineStageResult,
        next_action: str,
        user_message: str,
        shoe_recommendation=None,
        debug: dict[str, Any] | None = None,
    ) -> FullPipelineResponse:
        return FullPipelineResponse(
            overall_status=overall_status,
            capture_quality=capture_quality,
            measurement=measurement,
            landmark_validation=landmark_validation,
            scale_estimate=scale_estimate,
            shoe_recommendation=shoe_recommendation,
            next_action=next_action,
            user_message=user_message,
            debug=debug or {},
        )

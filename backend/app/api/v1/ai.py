import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.capture_session import CaptureSession
from app.models.foot_measurement import FootMeasurement
from app.models.scale_estimate import ScaleEstimate
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.schemas.ai import (
    AIProcessResponse,
    AIResultsResponse,
    AIStatusResponse,
    CaptureDeviceMetadata,
    CaptureQualityResult,
    ImageValidationResponse,
    MeasurementResponse,
)
from app.schemas.pipeline import FullPipelineRequest, FullPipelineResponse
from app.schemas.reference_object import (
    ReferenceObjectDetectionRequest,
    ReferenceObjectDetectionResponse,
)
from app.schemas.scale import ScaleEstimateRequest, ScaleEstimateResponse
from app.schemas.shoe_size import ShoeSizeRequest, ShoeSizeResponse
from app.services.ai_processing_service import AIProcessingService
from app.services.capture_metadata_service import CaptureMetadataService
from app.services.capture_quality_service import CaptureQualityService
from app.services.capture_consensus_service import CaptureConsensusService
from app.services.reference_object_detection_service import (
    ReferenceObjectDetectionResult,
    ReferenceObjectDetectionService,
)
from app.services.scan_service import FootScanService
from app.services.scale_estimate_persistence_service import ScaleEstimatePersistenceService
from app.services.scale_estimation_service import ScaleEstimateResult, ScaleEstimationService
from app.services.scan_orchestration_service import ScanOrchestrationService
from app.services.shoe_recommendation_persistence_service import ShoeRecommendationPersistenceService
from app.services.shoe_size_service import ShoeSizeService
from app.services.storage.s3_service import S3StorageService


router = APIRouter()


def _parse_device_metadata(raw_metadata: str | None) -> dict | None:
    if not raw_metadata:
        return None
    try:
        payload = json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="device_metadata must be valid JSON",
        ) from exc
    return CaptureDeviceMetadata.model_validate(payload).model_dump()


def _capture_quality_response(
    quality_payload: dict[str, Any],
    capture_session_id: UUID | None = None,
) -> dict[str, Any]:
    if capture_session_id is None:
        return quality_payload
    return {
        "capture_quality": quality_payload,
        "capture_session_id": str(capture_session_id),
    }


def _device_metadata_from_scan_payload(payload: dict[str, Any] | None) -> dict | None:
    if not payload:
        return None
    if "device_metadata" in payload:
        metadata = payload.get("device_metadata")
    else:
        metadata = payload
    if metadata is None:
        return None
    return CaptureDeviceMetadata.model_validate(metadata).model_dump()


def _uuid_from_payload(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="uploaded_image_id must be a valid UUID",
        ) from exc


def _latest_uploaded_image(db: Session, user: User, scan_id: UUID) -> UploadedImage | None:
    return db.scalar(
        select(UploadedImage)
        .where(
            UploadedImage.user_id == user.id,
            UploadedImage.foot_scan_id == scan_id,
            UploadedImage.upload_status == "uploaded",
        )
        .order_by(UploadedImage.created_at.desc())
    )


def _read_image_bytes(image: UploadedImage | None) -> bytes | None:
    if not image:
        return None
    try:
        return S3StorageService().get_object_bytes(image.bucket, image.object_key)
    except Exception:
        return None


def _run_reference_detection(
    request: Any,
    image_bytes: bytes | None,
) -> ReferenceObjectDetectionResult:
    payload = request.model_dump(mode="json") if hasattr(request, "model_dump") else dict(request)
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
    detection: ReferenceObjectDetectionResult,
) -> ScaleEstimateResult:
    return ScaleEstimateResult(
        scale_status="needs_reference",
        scale_mode="reference_object",
        pixels_per_mm=None,
        mm_per_pixel=None,
        confidence=detection.confidence,
        evidence={"reference_detection": detection.to_dict()},
        issues=detection.issues or ["Reference object was not detected."],
        instructions=detection.instructions
        or ["Place the reference object fully visible beside your foot and retake."],
    )


@router.post("/scans/{scan_id}/process", response_model=AIProcessResponse)
def process_scan(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIProcessResponse:
    validation = AIProcessingService(db).process_scan(current_user, scan_id)
    status = "validation_passed" if validation.valid else "validation_failed"
    return AIProcessResponse(
        scan_id=scan_id,
        status=status,
        message=(
            "Image validation passed. Measurement AI is not implemented yet."
            if validation.valid
            else "Image validation failed. Fix the image issues before AI processing."
        ),
        valid=validation.valid,
        issues=validation.issues,
        foot_count=validation.foot_count,
        segmentation_confidence=validation.segmentation_confidence,
        foot_bbox=validation.foot_bbox,
    )


@router.post("/scans/{scan_id}/validate", response_model=ImageValidationResponse)
def validate_scan_image(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImageValidationResponse:
    return AIProcessingService(db).validate_scan(current_user, scan_id)


@router.post("/capture-quality")
async def capture_quality_for_image(
    image: UploadFile = File(...),
    supporting_images: list[UploadFile] | None = File(default=None),
    device_metadata: str | None = Form(default=None),
    persist_session: bool = Form(default=False),
    foot_scan_id: UUID | None = Form(default=None),
    uploaded_image_id: UUID | None = Form(default=None),
    image_id: UUID | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload an image file.")
    metadata = _parse_device_metadata(device_metadata)
    image_bytes = await image.read()
    frames = [image_bytes]
    for supporting_image in supporting_images or []:
        if not supporting_image.content_type or not supporting_image.content_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload image frames only.")
        frames.append(await supporting_image.read())
    if len(frames) > 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A maximum of three frames is supported.")
    # This is the live-camera preflight. Keep it lightweight so a slow model
    # download or CPU inference can never leave the mobile UI on "Checking".
    quality_service = CaptureQualityService(enable_segmentation=False)
    analyses = [quality_service.analyze_bytes(frame, device_metadata=metadata) for frame in frames]
    consensus = CaptureConsensusService().combine(analyses)
    quality_payload = CaptureQualityResult.model_validate(
        consensus.to_dict()
    ).model_dump()
    if not persist_session:
        return _capture_quality_response(quality_payload)

    session = CaptureMetadataService(db).create_capture_session(
        current_user,
        capture_quality=quality_payload,
        device_metadata=metadata,
        foot_scan_id=foot_scan_id,
        uploaded_image_id=uploaded_image_id or image_id,
    )
    return _capture_quality_response(quality_payload, session.id)


@router.post("/scans/{scan_id}/capture-quality")
def capture_quality_for_scan(
    scan_id: UUID,
    payload: dict[str, Any] | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    device_metadata = _device_metadata_from_scan_payload(payload)
    try:
        result = AIProcessingService(db).capture_quality(
            current_user,
            scan_id,
            device_metadata=device_metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    quality_payload = CaptureQualityResult.model_validate(result.to_dict()).model_dump()
    if not payload or not payload.get("persist_session"):
        return _capture_quality_response(quality_payload)

    session = CaptureMetadataService(db).create_capture_session(
        current_user,
        capture_quality=quality_payload,
        device_metadata=device_metadata,
        foot_scan_id=scan_id,
        uploaded_image_id=_uuid_from_payload(payload.get("uploaded_image_id") or payload.get("image_id")),
    )
    return _capture_quality_response(quality_payload, session.id)


@router.post("/scans/{scan_id}/scale-estimate", response_model=ScaleEstimateResponse)
def estimate_scan_scale(
    scan_id: UUID,
    payload: ScaleEstimateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScaleEstimateResponse:
    scan = FootScanService(db).get_scan(current_user, scan_id)
    measurement = db.scalar(
        select(FootMeasurement)
        .where(FootMeasurement.scan_id == scan.id)
        .order_by(FootMeasurement.created_at.desc())
    )
    capture_session = db.scalar(
        select(CaptureSession)
        .where(CaptureSession.user_id == current_user.id, CaptureSession.foot_scan_id == scan.id)
        .order_by(CaptureSession.created_at.desc())
    )
    request = payload or ScaleEstimateRequest()
    reference_object = request.reference_object
    reference_detection = None
    if request.reference_object_detection and request.reference_object_detection.enabled:
        image = _latest_uploaded_image(db, current_user, scan.id)
        reference_detection = _run_reference_detection(
            request.reference_object_detection,
            _read_image_bytes(image),
        )
        if reference_detection.detected:
            reference_object = reference_detection.reference_object

    measurement_payload = (
        {
            "measurement_status": measurement.measurement_status,
            "foot_length_pixels": float(measurement.foot_length_pixels or 0),
            "foot_width_pixels": float(measurement.foot_width_pixels or 0),
            "heel_point": {"x": float(measurement.heel_x or 0), "y": float(measurement.heel_y or 0)},
            "toe_point": {"x": float(measurement.toe_x or 0), "y": float(measurement.toe_y or 0)},
            "width_points": {
                "left": {
                    "x": float(measurement.width_left_x or 0),
                    "y": float(measurement.width_left_y or 0),
                },
                "right": {
                    "x": float(measurement.width_right_x or 0),
                    "y": float(measurement.width_right_y or 0),
                },
            },
        }
        if measurement
        else {"measurement_status": "missing"}
    )
    result = (
        _needs_reference_scale_result(reference_detection)
        if reference_detection is not None and not reference_detection.detected
        else ScaleEstimationService().estimate_scale(
            measurement=measurement_payload,
            capture_session=capture_session,
            device_metadata=request.device_metadata,
            image_metadata=request.image_metadata,
            reference_object=reference_object,
            calibration_mat=request.calibration_mat,
            depth_metadata=request.depth_metadata,
        )
    )
    ScaleEstimatePersistenceService(db).persist_estimate(
        current_user,
        scan.id,
        result,
        foot_measurement_id=measurement.id if measurement else None,
        capture_session_id=capture_session.id if capture_session else None,
    )
    return ScaleEstimateResponse.model_validate(result.to_dict())


@router.post(
    "/scans/{scan_id}/detect-reference-object",
    response_model=ReferenceObjectDetectionResponse,
)
def detect_scan_reference_object(
    scan_id: UUID,
    payload: ReferenceObjectDetectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReferenceObjectDetectionResponse:
    scan = FootScanService(db).get_scan(current_user, scan_id)
    image = _latest_uploaded_image(db, current_user, scan.id)
    result = _run_reference_detection(payload, _read_image_bytes(image))
    return ReferenceObjectDetectionResponse.model_validate(result.to_dict())


@router.post("/scans/{scan_id}/shoe-size", response_model=ShoeSizeResponse)
def recommend_scan_shoe_size(
    scan_id: UUID,
    payload: ShoeSizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShoeSizeResponse:
    scan = FootScanService(db).get_scan(current_user, scan_id)
    measurement = db.scalar(
        select(FootMeasurement)
        .where(FootMeasurement.scan_id == scan.id)
        .order_by(FootMeasurement.created_at.desc())
    )
    scale_estimate = db.scalar(
        select(ScaleEstimate)
        .where(ScaleEstimate.user_id == current_user.id, ScaleEstimate.foot_scan_id == scan.id)
        .order_by(ScaleEstimate.created_at.desc())
    )
    capture_session = db.scalar(
        select(CaptureSession)
        .where(CaptureSession.user_id == current_user.id, CaptureSession.foot_scan_id == scan.id)
        .order_by(CaptureSession.created_at.desc())
    )
    service_request = ShoeSizeRequest(
        region=payload.region,
        gender=payload.gender,
        fit_preference=payload.fit_preference,
        shoe_type=payload.shoe_type,
        foot_length_mm=scale_estimate.foot_length_mm if scale_estimate else None,
        foot_width_mm=scale_estimate.foot_width_mm if scale_estimate else None,
        measurement_status=measurement.measurement_status if measurement else "missing",
        scale_status=scale_estimate.scale_status if scale_estimate else "unavailable",
        scale_confidence=scale_estimate.confidence if scale_estimate else 0.0,
        capture_status=capture_session.capture_status if capture_session else None,
    )
    response = ShoeSizeService().recommend_size(service_request)
    ShoeRecommendationPersistenceService(db).persist_recommendation(
        current_user,
        scan.id,
        service_request,
        response,
        scale_estimate_id=scale_estimate.id if scale_estimate else None,
    )
    return response


@router.post("/scans/{scan_id}/run-full-pipeline", response_model=FullPipelineResponse)
def run_scan_full_pipeline(
    scan_id: UUID,
    payload: FullPipelineRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FullPipelineResponse:
    return ScanOrchestrationService(db).run_full_pipeline(
        current_user,
        scan_id,
        payload or FullPipelineRequest(),
    )


@router.post("/scans/{scan_id}/measure", response_model=MeasurementResponse)
def measure_scan(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeasurementResponse:
    try:
        result = AIProcessingService(db).measure_scan(current_user, scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return MeasurementResponse(
        measurement_status=result.measurement_status,
        foot_length_pixels=result.foot_length_pixels,
        foot_width_pixels=result.foot_width_pixels,
        heel_point={"x": result.heel_point.x, "y": result.heel_point.y},
        toe_point={"x": result.toe_point.x, "y": result.toe_point.y},
        width_points={
            "left": {"x": result.width_left_point.x, "y": result.width_left_point.y},
            "right": {"x": result.width_right_point.x, "y": result.width_right_point.y},
        },
        confidence_score=result.confidence_score,
    )


@router.get("/scans/{scan_id}/status", response_model=AIStatusResponse)
def scan_ai_status(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIStatusResponse:
    scan = FootScanService(db).get_scan(current_user, scan_id)
    return AIStatusResponse(
        scan_id=scan.id,
        status=scan.status,
        processing_error=scan.processing_error,
        validation_status=scan.validation_status,
        validation_issues=scan.validation_issues,
    )


@router.get("/scans/{scan_id}/results", response_model=AIResultsResponse)
def scan_ai_results(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIResultsResponse:
    return AIProcessingService(db).results(current_user, scan_id)

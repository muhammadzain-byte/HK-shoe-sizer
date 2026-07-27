from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shoe_recommendation import ShoeRecommendation
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.services.ai.contracts import BoundingBox
from app.schemas.ai import AIResultsResponse, ImageValidationResponse
from app.services.capture_quality_service import CaptureQualityService
from app.services.image_validation_service import ImageValidationService
from app.services.measurement_service import FootMeasurementResult, MeasurementService
from app.services.scan_service import FootScanService
from app.services.storage.s3_service import S3StorageService


class AIProcessingService:
    def __init__(self, db: Session):
        self.db = db
        self.storage_service = S3StorageService()
        self._image_validation_service: ImageValidationService | None = None
        self.capture_quality_service = CaptureQualityService()
        self.measurement_service = MeasurementService()

    @property
    def image_validation_service(self) -> ImageValidationService:
        if self._image_validation_service is None:
            self._image_validation_service = ImageValidationService()
        return self._image_validation_service

    def process_scan(self, user: User, scan_id: UUID) -> ImageValidationResponse:
        scan = FootScanService(self.db).get_scan(user, scan_id)
        validation = self.validate_scan(user, scan_id)

        if not validation.valid:
            scan.status = "validation_failed"
            scan.processing_error = "; ".join(validation.issues)
            self.db.add(scan)
            self.db.commit()
            return validation

        scan.status = "validation_passed"
        scan.processing_error = None
        self.db.add(scan)
        self.db.commit()
        return validation

    def validate_scan(self, user: User, scan_id: UUID) -> ImageValidationResponse:
        scan = FootScanService(self.db).get_scan(user, scan_id)
        image = self._latest_uploaded_image(user, scan.id)

        if not image:
            issues = ["No uploaded image is attached to this scan"]
            scan.validation_status = "failed"
            scan.validation_issues = issues
            self.db.add(scan)
            self.db.commit()
            return ImageValidationResponse(valid=False, issues=issues)

        try:
            image_bytes = self.storage_service.get_object_bytes(image.bucket, image.object_key)
        except Exception:
            issues = ["Uploaded image could not be retrieved"]
            scan.validation_status = "failed"
            scan.validation_issues = issues
            scan.processing_error = "; ".join(issues)
            self.db.add(scan)
            self.db.commit()
            return ImageValidationResponse(valid=False, issues=issues)

        result = self.image_validation_service.validate(image_bytes)

        scan.validation_status = "passed" if result.valid else "failed"
        scan.validation_issues = result.issues
        if not result.valid:
            scan.processing_error = "; ".join(result.issues)
        self.db.add(scan)
        self.db.commit()
        return ImageValidationResponse(
            valid=result.valid,
            issues=result.issues,
            foot_count=result.foot_count,
            segmentation_confidence=result.segmentation_confidence,
            foot_bbox=self._bbox_payload(result.foot_bbox),
        )

    def capture_quality(
        self,
        user: User,
        scan_id: UUID,
        device_metadata: dict | None = None,
    ):
        scan = FootScanService(self.db).get_scan(user, scan_id)
        image = self._latest_uploaded_image(user, scan.id)
        if not image:
            raise ValueError("No uploaded image is attached to this scan.")
        image_bytes = self.storage_service.get_object_bytes(image.bucket, image.object_key)
        return self.capture_quality_service.analyze_bytes(image_bytes, device_metadata=device_metadata)

    def _bbox_payload(self, bbox: BoundingBox | None) -> dict[str, int] | None:
        if bbox is None:
            return None
        return {
            "x": bbox.x,
            "y": bbox.y,
            "width": bbox.width,
            "height": bbox.height,
        }

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

    def measure_scan(self, user: User, scan_id: UUID) -> FootMeasurementResult:
        scan = FootScanService(self.db).get_scan(user, scan_id)
        image = self._latest_uploaded_image(user, scan.id)
        if not image:
            raise ValueError("No uploaded image is attached to this scan.")

        image_bytes = self.storage_service.get_object_bytes(image.bucket, image.object_key)
        pil_image = self._image_from_bytes(image_bytes)
        segmentation = self.image_validation_service.foot_segmentation_service.segment(pil_image)
        selected = segmentation.feet[0] if segmentation.feet else None
        if not selected or selected.mask is None:
            raise ValueError("No selected foot mask is available for measurement.")

        result = self.measurement_service.measure_mask(
            selected.mask,
            float(segmentation.confidence_score) if segmentation.confidence_score is not None else None,
            refinement_metadata=(
                selected.diagnostics.get("refinement")
                if isinstance(selected.diagnostics, dict)
                else None
            ),
        )
        self.measurement_service.persist_result(self.db, scan.id, result)
        scan.status = "measured"
        self.db.add(scan)
        self.db.commit()
        return result

    def _image_from_bytes(self, image_bytes: bytes):
        from io import BytesIO

        from PIL import Image

        return Image.open(BytesIO(image_bytes)).convert("RGB")

    def results(self, user: User, scan_id: UUID) -> AIResultsResponse:
        scan = FootScanService(self.db).get_scan(user, scan_id)
        recommendations = list(
            self.db.scalars(
                select(ShoeRecommendation).where(ShoeRecommendation.foot_scan_id == scan.id)
            )
        )
        return AIResultsResponse(
            scan_id=scan.id,
            length_mm=scan.length_mm,
            width_mm=scan.width_mm,
            arch_height_mm=scan.arch_height_mm,
            confidence_score=scan.confidence_score,
            recommendations=recommendations,
        )

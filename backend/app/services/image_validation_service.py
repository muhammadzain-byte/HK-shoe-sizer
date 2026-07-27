from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageFilter, ImageStat

from app.services.ai.contracts import BoundingBox, FootSegmentationService, SegmentationResult
from app.services.ai.sam2_foot_segmentation_service import SAM2FootSegmentationService


@dataclass(frozen=True)
class ImageValidationResult:
    valid: bool
    issues: list[str]
    foot_count: int | None = None
    segmentation_confidence: float | None = None
    foot_bbox: BoundingBox | None = None


class ImageValidationService:
    def __init__(self, foot_segmentation_service: FootSegmentationService | None = None):
        self.foot_segmentation_service = foot_segmentation_service or SAM2FootSegmentationService()

    def validate(self, image_bytes: bytes) -> ImageValidationResult:
        issues: list[str] = []
        try:
            image = Image.open(BytesIO(image_bytes))
            image.verify()
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return ImageValidationResult(valid=False, issues=["Image file could not be read"])

        issues.extend(self._quality_issues(image))
        try:
            segmentation = self.foot_segmentation_service.segment(image)
            issues.extend(self._segmentation_issues(segmentation))
        except Exception:
            return ImageValidationResult(
                valid=False,
                issues=[*issues, "Foot segmentation could not be completed"],
            )

        return ImageValidationResult(
            valid=not issues,
            issues=issues,
            foot_count=segmentation.foot_count,
            segmentation_confidence=(
                float(segmentation.confidence_score) if segmentation.confidence_score else None
            ),
            foot_bbox=segmentation.foot_bbox,
        )

    def _quality_issues(self, image: Image.Image) -> list[str]:
        grayscale = image.convert("L")
        stat = ImageStat.Stat(grayscale)
        mean_luminance = stat.mean[0]

        histogram = grayscale.histogram()
        total_pixels = max(sum(histogram), 1)
        dark_ratio = sum(histogram[:35]) / total_pixels
        bright_ratio = sum(histogram[245:]) / total_pixels

        edge_image = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_variance = ImageStat.Stat(edge_image).var[0]

        issues: list[str] = []
        if edge_variance < 35:
            issues.append("Image is too blurry")
        if mean_luminance < 55 or dark_ratio > 0.45:
            issues.append("Lighting is too dark")
        if mean_luminance > 225 or bright_ratio > 0.35:
            issues.append("Image is overexposed")
        return issues

    def _segmentation_issues(self, segmentation: SegmentationResult) -> list[str]:
        issues: list[str] = []

        if segmentation.foot_count == 0:
            issues.append("No clear foot is visible")
        elif segmentation.foot_count > 1:
            issues.append("More than one foot is visible")

        if segmentation.edge_contact_detected:
            issues.append("Foot is partially outside frame")

        if segmentation.foot_bbox and self._likely_incorrect_camera_angle(segmentation.foot_bbox):
            issues.append("Camera angle is incorrect")

        return issues

    def _likely_incorrect_camera_angle(self, bbox: BoundingBox) -> bool:
        aspect_ratio = bbox.height / max(bbox.width, 1)
        inverse_aspect_ratio = bbox.width / max(bbox.height, 1)
        return aspect_ratio < 1.15 and inverse_aspect_ratio < 1.15

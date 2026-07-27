from decimal import Decimal

from app.services.ai.contracts import (
    FootSegmentationService,
    MeasurementResult,
    MeasurementService,
    RecommendationResult,
    SegmentationResult,
    SizeRecommendationService,
)


class PlaceholderFootSegmentationService(FootSegmentationService):
    def segment(self, image) -> SegmentationResult:
        return SegmentationResult(mask_uri=None, confidence_score=Decimal("0.0000"), model_name="placeholder")


class PlaceholderMeasurementService(MeasurementService):
    def measure(self, segmentation: SegmentationResult) -> MeasurementResult:
        return MeasurementResult(
            length_mm=None,
            width_mm=None,
            arch_height_mm=None,
            confidence_score=segmentation.confidence_score,
        )


class PlaceholderSizeRecommendationService(SizeRecommendationService):
    def recommend(self, measurement: MeasurementResult) -> list[RecommendationResult]:
        return [
            RecommendationResult(
                region="US",
                size_value="pending",
                width_category=None,
                brand=None,
                confidence_score=measurement.confidence_score,
                rationale="AI measurement is not enabled in this phase.",
            )
        ]

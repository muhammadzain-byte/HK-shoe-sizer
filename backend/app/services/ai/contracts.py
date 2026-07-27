from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SegmentedFoot:
    bbox: BoundingBox
    confidence_score: Decimal | None
    touches_frame_edge: bool
    area_pixels: int
    mask: Any | None = None
    diagnostics: dict[str, Any] | None = None


@dataclass(frozen=True)
class SegmentationResult:
    mask_uri: str | None
    confidence_score: Decimal | None
    model_name: str
    foot_count: int = 0
    foot_bbox: BoundingBox | None = None
    edge_contact_detected: bool = False
    feet: list[SegmentedFoot] | None = None


@dataclass(frozen=True)
class MeasurementResult:
    length_mm: Decimal | None
    width_mm: Decimal | None
    arch_height_mm: Decimal | None
    confidence_score: Decimal | None


@dataclass(frozen=True)
class RecommendationResult:
    region: str
    size_value: str
    width_category: str | None
    brand: str | None
    confidence_score: Decimal | None
    rationale: str | None


class FootSegmentationService(ABC):
    @abstractmethod
    def segment(self, image: Image.Image) -> SegmentationResult:
        raise NotImplementedError


class MeasurementService(ABC):
    @abstractmethod
    def measure(self, segmentation: SegmentationResult) -> MeasurementResult:
        raise NotImplementedError


class SizeRecommendationService(ABC):
    @abstractmethod
    def recommend(self, measurement: MeasurementResult) -> list[RecommendationResult]:
        raise NotImplementedError


class AIModelProvider(ABC):
    @abstractmethod
    def load_model(self, model_name: str) -> object:
        raise NotImplementedError

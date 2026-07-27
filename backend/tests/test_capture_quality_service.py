from __future__ import annotations

from decimal import Decimal

import numpy as np
from PIL import Image

from app.services.ai.contracts import BoundingBox, SegmentedFoot, SegmentationResult
from app.services.capture_quality_service import CaptureQualityService
from app.schemas.ai import CaptureDeviceMetadata


class FakeSegmentationService:
    def __init__(
        self,
        bbox: BoundingBox | None = None,
        foot_count: int = 1,
        lower_leg_ratio: float = 0.05,
    ) -> None:
        self.bbox = bbox or BoundingBox(x=330, y=170, width=340, height=930)
        self.foot_count = foot_count
        self.lower_leg_ratio = lower_leg_ratio

    def segment(self, image: Image.Image) -> SegmentationResult:
        foot = (
            SegmentedFoot(
                bbox=self.bbox,
                confidence_score=Decimal("0.90"),
                touches_frame_edge=False,
                area_pixels=self.bbox.width * self.bbox.height,
                diagnostics={
                    "refinement": {
                        "removed_lower_leg_area_ratio": self.lower_leg_ratio,
                    }
                },
            )
            if self.bbox is not None
            else None
        )
        return SegmentationResult(
            mask_uri=None,
            confidence_score=Decimal("0.90"),
            model_name="fake",
            foot_count=self.foot_count,
            foot_bbox=self.bbox,
            edge_contact_detected=False,
            feet=[foot] if foot else [],
        )


def textured_image(width: int = 1000, height: int = 1400, value: int = 140) -> Image.Image:
    rng = np.random.default_rng(42)
    noise = rng.normal(value, 18, (height, width, 3)).clip(0, 255).astype("uint8")
    return Image.fromarray(noise, mode="RGB")


def service(
    bbox: BoundingBox | None = None,
    foot_count: int = 1,
    lower_leg_ratio: float = 0.05,
) -> CaptureQualityService:
    return CaptureQualityService(FakeSegmentationService(bbox, foot_count, lower_leg_ratio))


def test_good_centered_foot_is_ready() -> None:
    result = service().analyze_image(textured_image())

    assert result.capture_status == "ready"
    assert result.score >= 0.82
    assert result.guidance["primary_instruction"] == "Ready to capture."


def test_toe_cropped_returns_instruction() -> None:
    result = service(BoundingBox(x=330, y=0, width=340, height=930)).analyze_image(textured_image())

    assert result.capture_status == "needs_adjustment"
    assert "toes_near_frame_edge" in result.issues
    assert "Keep all toes inside the frame." in result.instructions


def test_heel_missing_returns_instruction() -> None:
    result = service(BoundingBox(x=330, y=470, width=340, height=930)).analyze_image(textured_image())

    assert result.capture_status == "needs_adjustment"
    assert "heel_near_frame_edge" in result.issues
    assert "Show the full heel." in result.instructions


def test_lower_leg_too_visible_returns_instruction() -> None:
    result = service(lower_leg_ratio=0.31).analyze_image(textured_image())

    assert result.capture_status == "needs_adjustment"
    assert "lower_leg_too_visible" in result.issues
    assert "Move your leg back; too much lower leg is visible." in result.instructions


def test_foot_too_close_returns_instruction() -> None:
    result = service(BoundingBox(x=260, y=60, width=480, height=1220)).analyze_image(textured_image())

    assert result.capture_status == "needs_adjustment"
    assert "camera_too_close" in result.issues
    assert "Move phone slightly higher." in result.instructions


def test_foot_too_far_returns_instruction() -> None:
    result = service(BoundingBox(x=410, y=430, width=180, height=360)).analyze_image(textured_image())

    assert result.capture_status == "needs_adjustment"
    assert "camera_too_far" in result.issues
    assert "Move phone closer." in result.instructions


def test_blurry_image_rejects() -> None:
    image = Image.new("RGB", (1000, 1400), (140, 140, 140))
    result = service().analyze_image(image)

    assert result.capture_status == "reject"
    assert "image_blurry" in result.issues


def test_low_light_rejects() -> None:
    image = Image.new("RGB", (1000, 1400), (20, 20, 20))
    result = service().analyze_image(image)

    assert result.capture_status == "reject"
    assert "low_light" in result.issues


def test_multiple_feet_rejects() -> None:
    result = service(foot_count=2).analyze_image(textured_image())

    assert result.capture_status == "reject"
    assert "multiple_feet_detected" in result.issues
    assert "Keep one bare foot only." in result.instructions


def test_fast_capture_mode_does_not_initialise_sam2() -> None:
    image = Image.new("RGB", (600, 900), "white")
    pixels = np.asarray(image).copy()
    pixels[150:760, 220:390] = (130, 90, 70)
    result = CaptureQualityService(enable_segmentation=False)._fast_segment(Image.fromarray(pixels))

    assert result is not None
    assert result.model_name == "fast_capture_quality"
    assert result.foot_bbox is not None


def test_capture_metadata_keeps_native_ar_evidence_separate_from_browser_mode() -> None:
    metadata = CaptureDeviceMetadata.model_validate(
        {
            "capture_mode": "arcore",
            "ar_evidence": {"plane_confidence": 0.94, "distance_to_floor_mm": 780},
        }
    )

    assert metadata.capture_mode == "arcore"
    assert metadata.ar_evidence == {"plane_confidence": 0.94, "distance_to_floor_mm": 780}

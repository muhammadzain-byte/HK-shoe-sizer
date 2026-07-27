from io import BytesIO

from PIL import Image

from app.services.capture_quality_service import CaptureQualityService


def test_blank_bad_image_returns_structured_safe_guidance_without_segmentation() -> None:
    output = BytesIO()
    Image.new("RGB", (320, 240), color=(235, 235, 235)).save(output, format="PNG")

    result = CaptureQualityService().analyze_bytes(output.getvalue()).to_dict()

    assert result["success"] is False
    assert result["stage"] == "capture_quality"
    assert result["status"] == "reject"
    assert result["capture_status"] == "reject"
    assert result["issues"]
    assert result["instructions"]


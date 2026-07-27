from app.services.depth.depth_scale_adapter import DepthScaleAdapter
from app.services.scale_estimation_service import ScaleEstimationService


def trusted_measurement() -> dict:
    return {
        "measurement_status": "trusted",
        "foot_length_pixels": 2840.0,
        "foot_width_pixels": 980.0,
    }


def strong_depth_metadata() -> dict:
    return {
        "depth_available": True,
        "depth_mode": "arcore",
        "camera_intrinsics": {
            "fx": 1420.0,
            "fy": 1420.0,
            "cx": 540.0,
            "cy": 960.0,
            "width": 1080,
            "height": 1920,
        },
        "distance_to_foot_plane_mm": 710.0,
        "depth_confidence": 0.93,
        "plane_confidence": 0.92,
    }


def test_strong_depth_metadata_can_produce_scale_evidence() -> None:
    result = DepthScaleAdapter().estimate_scale(
        trusted_measurement(),
        strong_depth_metadata(),
        image_metadata={"width": 1080, "height": 1920},
        capture_session={"capture_status": "ready"},
    )

    assert result["scale_status"] == "available"
    assert result["scale_mode"] == "ar_depth"
    assert result["mm_per_pixel"] == 0.5
    assert result["pixels_per_mm"] == 2.0


def test_weak_depth_metadata_cannot_produce_mm_per_pixel() -> None:
    payload = strong_depth_metadata()
    payload["depth_confidence"] = 0.3

    result = DepthScaleAdapter().estimate_scale(
        trusted_measurement(),
        payload,
        image_metadata={"width": 1080, "height": 1920},
        capture_session={"capture_status": "ready"},
    )

    assert result["scale_status"] == "low_confidence"
    assert result["mm_per_pixel"] is None


def test_scale_estimation_service_uses_ar_depth_mode_only_when_safe() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        capture_session={"capture_status": "ready"},
        depth_metadata=strong_depth_metadata(),
        image_metadata={"width": 1080, "height": 1920},
    )

    assert result.scale_status == "available"
    assert result.scale_mode == "ar_depth"
    assert result.real_world_measurement.foot_length_mm == 1420.0


def test_measurement_not_trusted_blocks_depth_scale() -> None:
    measurement = {**trusted_measurement(), "measurement_status": "needs_review"}

    result = ScaleEstimationService().estimate_scale(
        measurement,
        capture_session={"capture_status": "ready"},
        depth_metadata=strong_depth_metadata(),
    )

    assert result.scale_status == "unavailable"
    assert result.mm_per_pixel is None
    assert "Measurement must be trusted before scale can be estimated." in result.issues


def test_capture_rejected_blocks_depth_scale() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        capture_session={"capture_status": "reject"},
        depth_metadata=strong_depth_metadata(),
    )

    assert result.scale_status == "unavailable"
    assert result.mm_per_pixel is None
    assert "Capture quality was rejected, so scale estimation is blocked." in result.issues

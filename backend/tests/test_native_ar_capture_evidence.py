from app.services.scale_estimation_service import ScaleEstimationService


def trusted_measurement() -> dict:
    return {
        "measurement_status": "trusted",
        "foot_length_pixels": 2000.0,
        "foot_width_pixels": 800.0,
    }


def arcore_evidence() -> dict:
    return {
        "depth_available": True,
        "depth_mode": "arcore",
        "camera_intrinsics": {"fx": 1400, "fy": 1400, "cx": 540, "cy": 960, "width": 1080, "height": 1920},
        "distance_to_foot_plane_mm": 700,
        "depth_confidence": 0.94,
        "plane_confidence": 0.93,
    }


def test_native_ar_evidence_is_used_when_no_request_depth_is_supplied() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        capture_session={
            "capture_status": "ready",
            "raw_device_metadata": {"capture_mode": "arcore", "ar_evidence": arcore_evidence()},
        },
        image_metadata={"width": 1080, "height": 1920},
    )

    assert result.scale_status == "available"
    assert result.scale_mode == "ar_depth"


def test_browser_metadata_cannot_supply_no_reference_scale() -> None:
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        capture_session={
            "capture_status": "ready",
            "raw_device_metadata": {"capture_mode": "browser_guidance", "ar_evidence": arcore_evidence()},
        },
        image_metadata={"width": 1080, "height": 1920},
    )

    assert result.scale_status == "unavailable"
    assert result.mm_per_pixel is None


def test_out_of_range_ar_distance_is_not_accepted() -> None:
    evidence = arcore_evidence()
    evidence["distance_to_foot_plane_mm"] = 80
    result = ScaleEstimationService().estimate_scale(
        trusted_measurement(),
        capture_session={
            "capture_status": "ready",
            "raw_device_metadata": {"capture_mode": "arcore", "ar_evidence": evidence},
        },
        image_metadata={"width": 1080, "height": 1920},
    )

    assert result.scale_status == "low_confidence"
    assert result.mm_per_pixel is None

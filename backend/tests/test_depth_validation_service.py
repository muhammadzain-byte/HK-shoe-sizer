from app.services.depth.depth_validation_service import DepthValidationService


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
        "distance_to_foot_plane_mm": 850.0,
        "depth_confidence": 0.92,
        "plane_confidence": 0.91,
    }


def test_missing_depth_returns_unavailable() -> None:
    result = DepthValidationService().validate(None)

    assert result.depth_status == "unavailable"
    assert result.can_support_scale is False


def test_depth_available_missing_intrinsics_returns_low_confidence() -> None:
    payload = strong_depth_metadata()
    payload["camera_intrinsics"] = {}

    result = DepthValidationService().validate(payload)

    assert result.depth_status == "low_confidence"
    assert "Camera intrinsics are incomplete." in result.issues


def test_low_plane_confidence_returns_low_confidence() -> None:
    payload = strong_depth_metadata()
    payload["plane_confidence"] = 0.4

    result = DepthValidationService().validate(payload)

    assert result.depth_status == "low_confidence"
    assert "Depth plane confidence is too low." in result.issues


def test_low_depth_confidence_returns_low_confidence() -> None:
    payload = strong_depth_metadata()
    payload["depth_confidence"] = 0.5

    result = DepthValidationService().validate(payload)

    assert result.depth_status == "low_confidence"
    assert "Depth confidence is too low." in result.issues


def test_strong_depth_metadata_returns_available() -> None:
    result = DepthValidationService().validate(strong_depth_metadata())

    assert result.depth_status == "available"
    assert result.depth_mode == "arcore"
    assert result.can_support_scale is True
    assert result.confidence == 0.91

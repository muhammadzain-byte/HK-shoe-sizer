from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_new_scan_auth_errors_are_not_backend_unreachable() -> None:
    component = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(
        encoding="utf-8"
    )

    assert "Session expired. Please sign in again." in component
    assert "Upload failed:" in component
    assert "Backend not reachable." in component


def test_bad_image_guidance_is_measurement_specific() -> None:
    component = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(
        encoding="utf-8"
    )

    assert "This image is not measurement-ready." in component
    assert "top-down photo of the full foot" in component
    assert "Avoid side-view images and cropped feet." in component

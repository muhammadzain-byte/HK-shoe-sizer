from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_new_scan_upload_state_machine_has_no_infinite_checking_state() -> None:
    source = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(
        encoding="utf-8"
    )

    for state in [
        "idle",
        "checking_backend",
        "backend_failed",
        "creating_scan",
        "uploading_image",
        "validating_capture",
        "processing_scan",
        "completed",
        "needs_adjustment",
        "failed",
    ]:
        assert state in source
    assert "setScanState(\"needs_adjustment\")" in source
    assert "setScanState(\"failed\")" in source
    assert "disabled={isUploading || backendStatus !== \"connected\"}" in source


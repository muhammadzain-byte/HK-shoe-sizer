from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_api_upload_and_scan_calls_have_stage_timeouts() -> None:
    api = (PROJECT_ROOT / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / "frontend" / "lib" / "scan-workflow.ts").read_text(encoding="utf-8")

    assert "timeoutMs: 15000" in api
    assert "timeoutMs: 30000" in api
    assert "withTimeoutSignal" in api
    assert "onStage?.(\"creating_scan\")" in workflow
    assert "onStage?.(\"uploading_image\")" in workflow
    assert "onStage?.(\"validating_capture\")" in workflow


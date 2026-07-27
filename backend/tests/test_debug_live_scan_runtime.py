from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_debug_live_scan_runtime_script_checks_scan_flow() -> None:
    source = (PROJECT_ROOT / "backend" / "scripts" / "debug_live_scan_runtime.py").read_text(
        encoding="utf-8"
    )

    for key in [
        "runtime_loaded",
        "backend_health_ok",
        "auth_ok",
        "auth_me_ok",
        "scan_create_ok",
        "local_upload_ok",
        "capture_quality_safe_response",
        "frontend_new_scan_ok",
        "ready_for_browser_scan_test",
    ]:
        assert key in source
    assert "/uploads/local" in source
    assert "/capture-quality" in source


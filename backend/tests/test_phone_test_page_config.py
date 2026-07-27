from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_phone_test_page_exposes_required_checks() -> None:
    source = (PROJECT_ROOT / "frontend" / "app" / "phone-test" / "page.tsx").read_text(encoding="utf-8")

    assert "Current browser URL" in source
    assert "Runtime API base" in source
    assert "Runtime backend health" in source
    assert "Test backend health" in source
    assert "Test auth/me" in source
    assert "Test tiny upload" in source
    assert "Your phone cannot reach the backend" in source
    assert "Refresh runtime config" in source


def test_api_runtime_config_is_cache_busted() -> None:
    source = (PROJECT_ROOT / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert "/local-stack.json?ts=${Date.now()}" in source
    assert 'cache: "no-store"' in source
    assert "resetRuntimeApiConfigForRetry" in source


def test_new_scan_debug_panel_has_runtime_refresh_button() -> None:
    source = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(encoding="utf-8")

    assert "Refresh runtime config" in source
    assert "run-app-now.ps1 -Force -Lan -PhoneAccess" in source

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_lan_runtime_uses_detected_ip_for_public_api_config() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "$runtimeHost = if ($Lan) { $lanIPv4 } else { \"localhost\" }" in source
    assert '"http://$runtimeHost`:$backendPort/api/v1"' in source
    assert '"http://$runtimeHost`:$backendPort"' in source
    assert "frontend\\public\\local-stack.json" in source
    assert "api_base_url = $apiBaseUrl" in source
    assert "backend_origin = $backendOrigin" in source


def test_public_runtime_exposes_phone_test_url_without_localhost_hardcode() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "phone_test_url = if ($Lan) { $phoneTestUrl } else { $null }" in source
    assert "$phoneTestUrl = \"$frontendUrl/phone-test\"" in source
    assert "http://localhost:3000/api/v1" not in source

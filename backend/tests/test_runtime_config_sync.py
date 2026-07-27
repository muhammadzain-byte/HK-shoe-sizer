from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_run_app_writes_runtime_config_to_frontend_public() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "local-stack.json" in source
    assert "frontend\\public" in source
    assert "api_base_url = $apiBaseUrl" in source
    assert "health_url = $healthUrl" in source
    assert "Start-Process powershell" in source
    assert "-Port $backendPort" in source
    assert "-Port $frontendPort" in source


def test_run_app_supports_lan_runtime_urls_and_cors() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "[switch]$Lan" in source
    assert "[string]$LanIp" in source
    assert "Get-LanIPv4Address" in source
    assert "$runtimeHost = if ($Lan) { $lanIPv4 } else { \"localhost\" }" in source
    assert "http://$runtimeHost`:$backendPort/api/v1" in source
    assert "http://localhost:$frontendPort" in source
    assert "http://127.0.0.1:$frontendPort" in source
    assert "http://$lanIPv4`:$frontendPort" in source
    assert "Phone New Scan:" in source
    assert "Phone Backend Health:" in source


def test_frontend_runtime_config_can_override_stale_env() -> None:
    source = (PROJECT_ROOT / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert "getRuntimeApiConfig" in source
    assert "/local-stack.json" in source
    assert "api_base_url: payload.api_base_url" in source
    assert "source: \"runtime\"" in source

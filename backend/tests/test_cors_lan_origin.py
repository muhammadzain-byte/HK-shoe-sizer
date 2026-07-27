from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_lan_cors_origin_is_dynamic() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert '"http://localhost:$frontendPort"' in source
    assert '"http://127.0.0.1:$frontendPort"' in source
    assert '"http://$lanIPv4`:$frontendPort"' in source
    assert "$env:CORS_ORIGINS = ($corsOrigins | Select-Object -Unique) -join \",\"" in source
    assert "http://192.168.2.107:3000" not in source


def test_research_models_remain_disabled_for_phone_access() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")
    backend_start = (PROJECT_ROOT / "scripts" / "start-testing-backend.ps1").read_text(encoding="utf-8")

    assert '$env:ENABLE_RESEARCH_MODELS = "false"' in source
    assert "ENABLE_RESEARCH_MODELS=$env:ENABLE_RESEARCH_MODELS" in source
    assert '$env:ENABLE_RESEARCH_MODELS = "false"' in backend_start

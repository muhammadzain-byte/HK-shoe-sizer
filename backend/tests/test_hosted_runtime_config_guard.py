from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_hosted_frontend_rejects_localhost_runtime_config() -> None:
    source = (PROJECT_ROOT / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert "function isLocalHostname" in source
    assert "isLocalHostname(window.location.hostname)" in source
    assert "isLocalHostname(configuredApiUrl.hostname)" in source

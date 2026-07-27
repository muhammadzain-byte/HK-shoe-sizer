import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_backend_connection_script_reports_expected_api_base(monkeypatch) -> None:
    from scripts import check_frontend_backend_connection as script

    def fake_fetch(url, timeout=20):
        if url.endswith("/health"):
            return True, 200, '{"status":"ok","database":"connected"}'
        return True, 200, "<html></html>"

    def fake_preflight(url, method, origin="http://localhost:3000", timeout=20):
        return True, 200, ""

    monkeypatch.setattr(script, "_fetch", fake_fetch)
    monkeypatch.setattr(script, "_cors_preflight", fake_preflight)
    monkeypatch.setattr(script, "_runtime", lambda: {})
    monkeypatch.setattr(script, "_env_local_api_base", lambda: "http://localhost:8000/api/v1")

    report = script.check_frontend_backend_connection()

    assert report["backend_health_ok"] is True
    assert report["auth_endpoints_reachable"] is True
    assert report["frontend_api_base_expected"] == "http://localhost:8000/api/v1"
    assert report["issues"] == []


def test_frontend_env_local_defines_api_base() -> None:
    env_local = PROJECT_ROOT / "frontend" / ".env.local"
    runtime_file = PROJECT_ROOT / "runtime" / "local-stack.json"
    expected_api_base = "http://localhost:8000/api/v1"
    if runtime_file.exists():
        expected_api_base = json.loads(runtime_file.read_text(encoding="utf-8-sig"))["api_base_url"]

    with open(env_local, encoding="utf-8-sig") as file:
        content = file.read()

    assert f"NEXT_PUBLIC_API_BASE_URL={expected_api_base}" in content

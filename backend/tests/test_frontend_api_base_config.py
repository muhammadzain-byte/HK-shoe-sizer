import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_api_base_url_is_consistent() -> None:
    env_local = (PROJECT_ROOT / "frontend" / ".env.local").read_text(encoding="utf-8")
    api_client = (PROJECT_ROOT / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")
    runtime_file = PROJECT_ROOT / "runtime" / "local-stack.json"
    expected_api_base = "http://localhost:8000/api/v1"
    if runtime_file.exists():
        expected_api_base = json.loads(runtime_file.read_text(encoding="utf-8-sig"))["api_base_url"]

    assert f"NEXT_PUBLIC_API_BASE_URL={expected_api_base}" in env_local
    assert 'process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"' in api_client


def test_new_scan_uses_shared_api_client() -> None:
    workflow = (PROJECT_ROOT / "frontend" / "lib" / "scan-workflow.ts").read_text(encoding="utf-8")
    component = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(
        encoding="utf-8"
    )

    assert "uploadLocalValidationImage" in workflow
    assert "checkScanCaptureQuality" in workflow
    assert "API_BASE_URL" in component
    assert "fetch(" not in component

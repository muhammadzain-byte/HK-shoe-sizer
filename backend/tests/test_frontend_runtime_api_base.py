from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_uses_next_public_api_base_and_runtime_launcher_message() -> None:
    api_source = (PROJECT_ROOT / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")
    auth_source = (PROJECT_ROOT / "frontend" / "components" / "auth-card.tsx").read_text(encoding="utf-8")

    assert "process.env.NEXT_PUBLIC_API_BASE_URL" in api_source
    assert "process.env.NEXT_PUBLIC_BACKEND_ORIGIN" in api_source
    assert "run-app-now.ps1 -Force" in api_source
    assert "sqlite_testing_fallback" in auth_source

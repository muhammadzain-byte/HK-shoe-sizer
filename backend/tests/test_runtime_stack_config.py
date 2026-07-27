from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_stack_config_has_selected_url_fields_in_launcher() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    for field in [
        "backend_port",
        "frontend_port",
        "api_base_url",
        "backend_origin",
        "frontend_url",
        "health_url",
        "new_scan_url",
        "validation_url",
        "database_mode",
    ]:
        assert field in source


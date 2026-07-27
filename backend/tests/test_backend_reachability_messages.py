from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backend_reachability_message_points_to_restart_script() -> None:
    component = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(
        encoding="utf-8"
    )
    checker = (PROJECT_ROOT / "backend" / "scripts" / "check_backend_health.py").read_text(
        encoding="utf-8"
    )

    assert "run-app-now.ps1 -Force" in component
    assert "restart-local-testing-stack.ps1 -Force" in checker or "run-app-now.ps1 -Force" in checker


def test_backend_health_contract_includes_phase6f_fields() -> None:
    router = (PROJECT_ROOT / "backend" / "app" / "api" / "v1" / "router.py").read_text(
        encoding="utf-8"
    )

    assert '"auth_ready": auth_ready' in router
    assert '"local_upload_ready": local_upload_ready' in router
    assert '"issues": issues' in router

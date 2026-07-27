from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_free_port_script_contains_emergency_port_candidates() -> None:
    source = (PROJECT_ROOT / "scripts" / "find-free-port.ps1").read_text(encoding="utf-8")

    assert "8020, 8000, 8010, 8011, 8012, 8021, 8030" in source
    assert "TcpListener" in source
    assert "selected_port" in source


def test_run_app_now_writes_runtime_stack_config() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "local-stack.json" in source
    assert "backend_port" in source
    assert "frontend_port" in source
    assert "api_base_url" in source
    assert "health_url" in source

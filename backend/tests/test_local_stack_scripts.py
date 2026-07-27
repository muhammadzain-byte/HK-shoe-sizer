from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_local_stack_scripts_exist_and_reference_expected_ports() -> None:
    diagnose = PROJECT_ROOT / "scripts" / "diagnose-local-stack.ps1"
    stop = PROJECT_ROOT / "scripts" / "stop-local-stack.ps1"
    restart = PROJECT_ROOT / "scripts" / "restart-local-testing-stack.ps1"

    assert diagnose.exists()
    assert stop.exists()
    assert restart.exists()
    diagnose_text = diagnose.read_text(encoding="utf-8")
    assert "Get-PortReport -Port 3000" in diagnose_text
    assert "Get-PortReport -Port 8000" in diagnose_text
    stop_text = stop.read_text(encoding="utf-8")
    assert "3000, 3010, 3011, 3020, 8000, 8010, 8011, 8012, 8020, 8021, 8030" in stop_text
    assert "Get-ListeningProcess -Port $port" in stop_text


def test_stop_local_stack_only_targets_app_ports() -> None:
    script = (PROJECT_ROOT / "scripts" / "stop-local-stack.ps1").read_text(encoding="utf-8")

    assert "3000, 3010, 3011, 3020, 8000, 8010, 8011, 8012, 8020, 8021, 8030" in script
    assert "Get-ListeningProcess -Port $port" in script
    assert "8010" in script
    assert "3010" in script
    assert "Stop-Process" in script
    assert "postgres" not in script.lower()
    assert "chrome" not in script.lower()


def test_restart_script_sets_local_testing_safety_flags() -> None:
    script = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")
    restart = (PROJECT_ROOT / "scripts" / "restart-local-testing-stack.ps1").read_text(encoding="utf-8")

    assert "ENABLE_RESEARCH_MODELS" in script
    assert '"false"' in script
    assert "NEXT_PUBLIC_API_BASE_URL" in script
    assert "new_scan_url" in script
    assert "run-app-now.ps1" in restart

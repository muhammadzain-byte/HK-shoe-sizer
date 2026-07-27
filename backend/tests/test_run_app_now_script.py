from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_run_app_now_script_guarantees_urls_and_dev_user_contract() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "Select-FreePort" in source
    assert "Try-PostgresRecovery" in source
    assert "sqlite_testing_fallback" in source
    assert "create_dev_user.py" in source
    assert "zaintariq1822@gmail.com" in source
    assert "TestPassword123!" in source
    assert "Backend health:" in source
    assert "New Scan:" in source
    assert "Validation:" in source


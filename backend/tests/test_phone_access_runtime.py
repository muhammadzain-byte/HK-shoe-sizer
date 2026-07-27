import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_run_app_now_supports_phone_access_mode() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "[switch]$PhoneAccess" in source
    assert "[switch]$FixFirewall" in source
    assert "if ($PhoneAccess -and -not $Lan)" in source
    assert "PHONE TEST URLS:" in source
    assert "diagnose-phone-access.ps1" in source
    assert "fix-phone-firewall.ps1" in source
    assert "artifacts\\phone-access" in source


def test_phone_url_artifact_contains_expected_routes() -> None:
    source = (PROJECT_ROOT / "scripts" / "run-app-now.ps1").read_text(encoding="utf-8")

    assert "phone-url.txt" in source
    assert "Frontend: $frontendUrl" in source
    assert "New Scan: $newScanUrl" in source
    assert "Validation: $validationUrl" in source
    assert "Phone Test: $phoneTestUrl" in source
    assert "Backend Health: $healthUrl" in source


def test_phone_diagnostic_script_does_not_crash() -> None:
    script = PROJECT_ROOT / "scripts" / "diagnose-phone-access.ps1"

    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OPEN THESE ON PHONE:" in result.stdout

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_new_scan_backend_status_has_timeout_and_terminal_states() -> None:
    source = (PROJECT_ROOT / "frontend" / "components" / "new-scan-workflow.tsx").read_text(
        encoding="utf-8"
    )

    for status in [
        "checking",
        "connected",
        "not_connected",
        "timeout",
        "database_unavailable",
        "wrong_port",
    ]:
        assert status in source
    assert "getApiHealth" in source
    assert "Retry backend check" in source
    assert "Copy restart command" in source
    assert "Backend check timed out after 5 seconds" in source


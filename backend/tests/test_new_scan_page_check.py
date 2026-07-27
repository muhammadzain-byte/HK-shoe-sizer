def test_new_scan_page_check_reports_recovery_command_when_unreachable() -> None:
    from scripts.check_new_scan_page import check_new_scan_page

    report = check_new_scan_page("http://127.0.0.1:9/scans/new")

    assert report["new_scan_page_ok"] is False
    assert any("restart-local-testing-stack.ps1 -Force" in step for step in report["next_steps"])

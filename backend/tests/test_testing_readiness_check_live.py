def test_testing_readiness_check_gives_next_commands_when_db_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.run_testing_readiness_check import run_testing_readiness_check

    report = run_testing_readiness_check()

    assert report["database_ready"] is False
    assert report["end_to_end_testing_ready"] is False
    assert any("setup-local-testing-db" in command for command in report["commands_to_run_next"])

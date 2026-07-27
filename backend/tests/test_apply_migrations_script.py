def test_apply_migrations_refuses_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.apply_migrations import apply_migrations

    report = apply_migrations()

    assert report["database_url_present"] is False
    assert report["ready"] is False
    assert "DATABASE_URL is not set." in report["issues"]

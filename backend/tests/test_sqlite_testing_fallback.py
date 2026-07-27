from pathlib import Path

from scripts.bootstrap_sqlite_testing_db import bootstrap_sqlite_testing_db


def test_sqlite_testing_fallback_bootstraps_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "local_testing.db"
    report = bootstrap_sqlite_testing_db(f"sqlite:///{db_path.as_posix()}")

    assert report["ready"] is True
    assert report["database_mode"] == "sqlite_testing_fallback"
    assert report["sqlite_testing_fallback"] is True
    assert report["expected_tables"]["users"] is True
    assert report["expected_tables"]["validation_cases"] is True
    assert "not production accuracy evidence" in report["warning"]


def test_sqlite_testing_fallback_refuses_postgresql_url() -> None:
    report = bootstrap_sqlite_testing_db("postgresql+psycopg://u:p@localhost/db")

    assert report["ready"] is False
    assert report["sqlite_testing_fallback"] is False


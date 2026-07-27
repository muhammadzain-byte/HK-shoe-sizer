from pathlib import Path


def test_setup_local_testing_db_script_exists() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "setup-local-testing-db.ps1"

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "Docker.DockerDesktop" in text
    assert "postgresql+psycopg://" in text

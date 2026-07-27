from pathlib import Path


def test_smoke_test_local_upload_uses_temp_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.smoke_test_local_upload import smoke_test_local_upload

    report = smoke_test_local_upload(str(tmp_path))

    assert report["local_storage_ready"] is True
    assert report["file_saved"] is True
    assert report["db_record_created"] is False
    assert any("DATABASE_URL" in issue for issue in report["issues"])

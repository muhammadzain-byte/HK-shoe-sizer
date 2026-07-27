import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")


def test_new_scan_flow_smoke_success(monkeypatch) -> None:
    from scripts import smoke_test_new_scan_flow as script

    def fake_db_ready(database_url):
        return {"database_ready": True, "issues": []}

    def fake_dev_user():
        return {"dev_user_ready": True, "issues": []}

    def fake_request_json(method, url, payload=None, token=None, timeout=120):
        if url.endswith("/auth/login"):
            return 200, {"access_token": "token"}
        if url.endswith("/scans") and method == "POST":
            return 201, {"id": "scan-1"}
        if url.endswith("/scans/scan-1") and method == "GET":
            return 200, {"uploaded_images": [{"id": "image-1"}]}
        if url.endswith("/ai/scans/scan-1/capture-quality"):
            return 200, {
                "capture_status": "reject",
                "issues": ["no_foot_detected"],
                "instructions": ["Use a top-down photo."],
            }
        return 404, {}

    monkeypatch.setattr(script, "verify_database_readiness", fake_db_ready)
    monkeypatch.setattr(script, "create_dev_user", fake_dev_user)
    monkeypatch.setattr(script, "_request_json", fake_request_json)
    monkeypatch.setattr(script, "_upload_image", lambda *args, **kwargs: (201, {"image_id": "image-1"}))

    report = script.smoke_test_new_scan_flow()

    assert report["ready_for_real_scan_testing"] is True
    assert report["bad_image_rejected_safely"] is True


def test_new_scan_flow_smoke_reports_missing_db(monkeypatch) -> None:
    from scripts import smoke_test_new_scan_flow as script

    monkeypatch.setattr(
        script,
        "verify_database_readiness",
        lambda database_url: {"database_ready": False, "issues": ["missing db"]},
    )

    report = script.smoke_test_new_scan_flow()

    assert report["ready_for_real_scan_testing"] is False
    assert report["db_ready"] is False
    assert report["issues"]

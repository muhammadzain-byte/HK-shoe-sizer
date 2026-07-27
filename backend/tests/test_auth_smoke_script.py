import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")


def test_auth_smoke_script_handles_missing_db_safely() -> None:
    from scripts.smoke_test_auth_flow import smoke_test_auth_flow

    report = smoke_test_auth_flow(database_url="not-a-sqlalchemy-url")

    assert report["backend_auth_ready"] is False
    assert report["database_connected"] is False
    assert report["issues"]


def test_auth_smoke_login_uses_app_email_not_database_username(monkeypatch) -> None:
    from scripts import smoke_test_auth_flow as script

    calls = []

    def fake_database_connected(_: str) -> tuple[bool, None]:
        return True, None

    def fake_request_json(method, url, payload=None, token=None, timeout=20):
        calls.append({"method": method, "url": url, "payload": payload, "token": token})
        if url.endswith("/auth/register"):
            return 201, {"email": "localtest@example.com"}
        if url.endswith("/auth/login"):
            return 200, {"access_token": "test-token", "token_type": "bearer"}
        if url.endswith("/auth/me"):
            return 200, {"email": "localtest@example.com"}
        return 404, {}

    monkeypatch.setattr(script, "_database_connected", fake_database_connected)
    monkeypatch.setattr(script, "_request_json", fake_request_json)

    report = script.smoke_test_auth_flow()

    login_payload = next(call["payload"] for call in calls if call["url"].endswith("/auth/login"))
    assert report["backend_auth_ready"] is True
    assert login_payload["email"] == "localtest@example.com"
    assert login_payload["email"] != "juta_user"

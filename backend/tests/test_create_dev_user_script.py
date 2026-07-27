import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")


def test_create_dev_user_creates_app_user_not_database_user(monkeypatch) -> None:
    from scripts import create_dev_user as script

    created_users = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def scalar(self, statement):
            return None

        def add(self, user):
            created_users.append(user)

        def commit(self):
            return None

    monkeypatch.setattr(script, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(script, "hash_password", lambda password: f"hashed:{password}")

    report = script.create_dev_user()

    assert report["dev_user_ready"] is True
    assert report["email"] == "zaintariq1822@gmail.com"
    assert report["email"] != "juta_user"
    assert created_users[0].email == "zaintariq1822@gmail.com"
    assert created_users[0].password_hash == "hashed:TestPassword123!"

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_refuses_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(
            app_env="production",
            JWT_SECRET_KEY="dev-only-change-me",
            STORAGE_BACKEND="s3",
            CORS_ORIGINS="https://app.example.com",
        )


def test_production_refuses_local_upload_storage() -> None:
    with pytest.raises(ValidationError, match="Local public upload storage"):
        Settings(
            app_env="production",
            JWT_SECRET_KEY="strong-test-secret",
            storage_backend="local",
            CORS_ORIGINS="https://app.example.com",
        )


def test_production_refuses_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(
            app_env="production",
            JWT_SECRET_KEY="strong-test-secret",
            STORAGE_BACKEND="s3",
            CORS_ORIGINS="*",
        )


def test_production_refuses_sqlite_testing_fallback() -> None:
    with pytest.raises(ValidationError, match="LOCAL_TESTING_DB_FALLBACK"):
        Settings(
            app_env="production",
            JWT_SECRET_KEY="strong-test-secret",
            STORAGE_BACKEND="s3",
            CORS_ORIGINS="https://app.example.com",
            LOCAL_TESTING_DB_FALLBACK=True,
        )


def test_production_requires_postgres() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            app_env="production",
            JWT_SECRET_KEY="strong-test-secret",
            STORAGE_BACKEND="s3",
            CORS_ORIGINS="https://app.example.com",
            DATABASE_URL="sqlite:///production.db",
        )

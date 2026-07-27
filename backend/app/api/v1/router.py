from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import create_engine, inspect

from app.api.v1 import ai, auth, capture_sessions, scans, uploads, users, validation_cases
from app.core.config import settings


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(capture_sessions.router, prefix="/capture-sessions", tags=["capture-sessions"])
api_router.include_router(validation_cases.router, prefix="/validation-cases", tags=["validation-cases"])


@api_router.get("", tags=["health"])
@api_router.get("/", tags=["health"])
def api_root() -> dict[str, str]:
    return {
        "service": "MirrorStep API",
        "status": "running",
        "health_url": "/api/v1/health",
        "docs_url": "/docs",
    }


@api_router.get("/health", tags=["health"])
def api_health() -> dict[str, object]:
    database = "disconnected"
    database_mode = "missing"
    validation_tables = False
    auth_ready = False
    local_upload_ready = False
    issues: list[str] = []
    is_sqlite_fallback = settings.local_testing_db_fallback or settings.database_url.startswith("sqlite")
    try:
        engine = create_engine(
            settings.database_url,
            future=True,
            connect_args={"connect_timeout": 5} if settings.database_url.startswith("postgresql") else {},
        )
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            validation_tables = {"validation_cases", "validation_benchmark_results"}.issubset(tables)
            auth_ready = {"users"}.issubset(tables) and bool(settings.jwt_secret_key)
            database_mode = "sqlite_testing_fallback" if is_sqlite_fallback else "postgresql"
            database = "sqlite_testing_fallback" if is_sqlite_fallback else "connected"
            if is_sqlite_fallback:
                issues.append("SQLite fallback is for local UI testing only, not production accuracy evidence.")
            if not validation_tables:
                issues.append("Validation tables are missing.")
            if not auth_ready:
                issues.append("Auth tables or JWT secret are missing.")
    except Exception as exc:
        database = "disconnected"
        database_mode = "missing"
        issues.append(f"Database connection failed: {exc}")

    if settings.storage_backend == "local":
        try:
            Path(settings.local_storage_dir).mkdir(parents=True, exist_ok=True)
            local_upload_ready = Path(settings.local_storage_dir).exists()
        except Exception as exc:
            issues.append(f"Local upload storage is not ready: {exc}")
    else:
        local_upload_ready = bool(settings.aws_s3_bucket)
        if not local_upload_ready:
            issues.append("Upload storage is not configured.")

    all_ready = database == "connected" and validation_tables and auth_ready and local_upload_ready
    if is_sqlite_fallback:
        all_ready = database == "sqlite_testing_fallback" and validation_tables and auth_ready and local_upload_ready
    return {
        "status": "ok" if all_ready else "error",
        "database": database,
        "database_mode": database_mode,
        "validation_tables": validation_tables,
        "auth_ready": auth_ready,
        "local_upload_ready": local_upload_ready,
        "research_models_enabled": settings.enable_research_models,
        "issues": issues,
    }

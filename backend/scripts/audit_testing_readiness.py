from __future__ import annotations

import importlib
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def audit_testing_readiness() -> dict[str, Any]:
    issues: list[str] = []
    next_steps: list[str] = []
    database_url = os.environ.get("DATABASE_URL")
    db_connected = False
    validation_tables = {"validation_cases": False, "validation_benchmark_results": False}

    backend_ready = _import_ok("app.main", issues)
    frontend_ready = (FRONTEND_DIR / "app").exists()
    migrations_ready = all(
        (BACKEND_DIR / "alembic" / "versions" / filename).exists()
        for filename in ("0007_validation_cases.py", "0008_validation_benchmark_results.py")
    )
    if not migrations_ready:
        issues.append("Required validation migrations are missing.")

    if database_url:
        try:
            engine = create_engine(database_url, future=True)
            with engine.connect() as connection:
                db_connected = True
                table_names = set(inspect(connection).get_table_names())
                validation_tables = {table: table in table_names for table in validation_tables}
        except SQLAlchemyError as exc:
            issues.append(f"Database connection failed: {exc}")
            next_steps.append("Start the local testing database and verify DATABASE_URL.")
    else:
        issues.append("DATABASE_URL is not set.")
        next_steps.append("Set DATABASE_URL or run scripts/start-testing-backend.ps1.")

    storage_ready = _storage_ready(issues, next_steps)
    validation_cockpit_ready = all(
        [
            (FRONTEND_DIR / "app" / "validation" / "page.tsx").exists(),
            (FRONTEND_DIR / "components" / "validation" / "ReferenceObjectAnnotator.tsx").exists(),
            _import_ok("app.api.v1.validation_cases", issues),
            _import_ok("app.services.validation_benchmark_service", issues),
            _import_ok("app.services.validation_accuracy_report_service", issues),
        ]
    )
    if os.environ.get("ENABLE_RESEARCH_MODELS", "false").lower() not in {"0", "false", "no", ""}:
        issues.append("ENABLE_RESEARCH_MODELS is not disabled.")

    alembic_info = _alembic_info()
    database_ready = db_connected and all(validation_tables.values())
    ready = all(
        [
            backend_ready,
            frontend_ready,
            database_ready,
            migrations_ready,
            storage_ready,
            validation_cockpit_ready,
        ]
    )
    return {
        "ready_for_testing": ready,
        "backend_ready": backend_ready,
        "frontend_ready": frontend_ready,
        "database_ready": database_ready,
        "migrations_ready": migrations_ready,
        "storage_ready": storage_ready,
        "validation_cockpit_ready": validation_cockpit_ready,
        "database_url_present": bool(database_url),
        "database_connection_ok": db_connected,
        "validation_tables": validation_tables,
        "alembic_current_revision": alembic_info.get("current_revision"),
        "alembic_head_revision": alembic_info.get("head_revision"),
        "lan_ip": _lan_ip(),
        "issues": issues,
        "next_steps": next_steps,
    }


def _import_ok(module: str, issues: list[str]) -> bool:
    try:
        importlib.import_module(module)
        return True
    except Exception as exc:
        issues.append(f"Import failed for {module}: {exc}")
        return False


def _storage_ready(issues: list[str], next_steps: list[str]) -> bool:
    storage_backend = os.environ.get("STORAGE_BACKEND", "local")
    if storage_backend == "local":
        storage_dir = BACKEND_DIR / os.environ.get("LOCAL_STORAGE_DIR", "storage/uploads")
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir.exists()
    if not os.environ.get("AWS_S3_BUCKET"):
        issues.append("AWS_S3_BUCKET is missing for non-local storage.")
        next_steps.append("Use STORAGE_BACKEND=local for local testing.")
        return False
    return True


def _alembic_info() -> dict[str, str | None]:
    config_path = BACKEND_DIR / "alembic.ini"
    if not config_path.exists():
        return {"current_revision": None, "head_revision": None}
    try:
        config = Config(str(config_path))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        script = ScriptDirectory.from_config(config)
        return {"current_revision": None, "head_revision": script.get_current_head()}
    except Exception:
        return {"current_revision": None, "head_revision": None}


def _lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def main() -> int:
    report = audit_testing_readiness()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

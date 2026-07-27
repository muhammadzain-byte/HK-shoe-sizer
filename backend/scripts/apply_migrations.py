from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]
VALIDATION_TABLES = ["validation_cases", "validation_benchmark_results"]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def apply_migrations(database_url: str | None = None) -> dict[str, Any]:
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        return {
            "database_url_present": False,
            "migration_applied": False,
            "validation_tables_exist": False,
            "ready": False,
            "issues": ["DATABASE_URL is not set."],
            "next_steps": ["Set DATABASE_URL and start the local testing database."],
        }

    if database_url.startswith("sqlite"):
        from scripts.bootstrap_sqlite_testing_db import bootstrap_sqlite_testing_db

        bootstrap = bootstrap_sqlite_testing_db(database_url)
        return {
            "database_url_present": True,
            "database_mode": "sqlite_testing_fallback",
            "migration_applied": False,
            "sqlite_bootstrap_applied": bool(bootstrap.get("ready")),
            "validation_tables_exist": bool(bootstrap.get("expected_tables", {}).get("validation_cases"))
            and bool(bootstrap.get("expected_tables", {}).get("validation_benchmark_results")),
            "ready": bool(bootstrap.get("ready")),
            "issues": bootstrap.get("issues", []),
            "next_steps": []
            if bootstrap.get("ready")
            else ["Review SQLite fallback bootstrap errors before starting the local app."],
            "warning": "SQLite fallback is for local UI testing only, not production accuracy evidence.",
        }

    env = os.environ.copy()
    database_url = _with_connect_timeout(database_url)
    env["DATABASE_URL"] = database_url
    env.setdefault("JWT_SECRET_KEY", "dev-only-change-me")
    env.setdefault("AWS_S3_BUCKET", "women-shoe-sizing-local")
    env.setdefault("STORAGE_BACKEND", "local")
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    try:
        result = subprocess.run(
            command,
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return {
            "database_url_present": True,
            "migration_applied": False,
            "validation_tables_exist": False,
            "ready": False,
            "issues": ["Alembic timed out while waiting for the database."],
            "next_steps": ["Start PostgreSQL on localhost:5432, then rerun the restart script."],
        }
    issues: list[str] = []
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "Alembic failed.").strip()
        if "ConnectionTimeout" in output or "connection timeout" in output:
            issues.append("PostgreSQL is not reachable at localhost:5432.")
        else:
            issues.append(output)
        return {
            "database_url_present": True,
            "migration_applied": False,
            "validation_tables_exist": False,
            "ready": False,
            "issues": issues,
            "next_steps": ["Start PostgreSQL on localhost:5432, then rerun the restart script."],
        }

    tables_exist = _validation_tables_exist(database_url, issues)
    return {
        "database_url_present": True,
        "migration_applied": True,
        "validation_tables_exist": tables_exist,
        "ready": tables_exist and not issues,
        "issues": issues,
        "next_steps": [] if tables_exist else ["Verify migrations 0007 and 0008."],
    }


def _validation_tables_exist(database_url: str, issues: list[str]) -> bool:
    try:
        engine = create_engine(_with_connect_timeout(database_url), future=True)
        with engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names())
    except Exception as exc:
        issues.append(f"Could not verify validation tables: {exc}")
        return False
    missing = [table for table in VALIDATION_TABLES if table not in table_names]
    if missing:
        issues.append(f"Missing validation tables: {', '.join(missing)}")
    return not missing


def _with_connect_timeout(database_url: str) -> str:
    if "postgresql" not in database_url or "connect_timeout=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}connect_timeout=5"


def main() -> int:
    report = apply_migrations()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from alembic.runtime.migration import MigrationContext
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


EXPECTED_TABLES = [
    "users",
    "foot_scans",
    "uploaded_images",
    "foot_measurements",
    "capture_sessions",
    "scale_estimates",
    "shoe_recommendations",
    "validation_cases",
    "validation_benchmark_results",
]

EXPECTED_INDEX_HINTS = {
    "capture_sessions": [
        "user_id",
        "foot_scan_id",
        "uploaded_image_id",
        "capture_status",
        "created_at",
    ],
    "scale_estimates": [
        "user_id",
        "foot_scan_id",
        "capture_session_id",
        "scale_status",
        "scale_mode",
        "created_at",
    ],
    "shoe_recommendations": ["user_id"],
}


def verify_database_readiness(database_url: str | None = None) -> dict[str, Any]:
    database_url_present = bool(database_url or os.environ.get("DATABASE_URL"))
    if not database_url:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            return _result(
                database_ready=False,
                issues=["DATABASE_URL is not set."],
                instructions=["Start the testing database and set DATABASE_URL."],
                database_url_present=False,
            )

    database_mode = _database_mode(database_url)
    database_url = _with_connect_timeout(database_url)
    try:
        engine = create_engine(database_url, future=True)
    except Exception as exc:
        return _result(
            database_ready=False,
            issues=[f"Could not create database engine: {exc}"],
            instructions=["Check DATABASE_URL and database driver installation."],
        )

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            table_names = set(inspector.get_table_names())
            current_revision = None if database_mode == "sqlite_testing_fallback" else _current_revision(connection)
            head_revision = _head_revision()
            expected_tables = {table: table in table_names for table in EXPECTED_TABLES}
            missing_tables = [table for table, exists in expected_tables.items() if not exists]
            index_report = _index_report(inspector, table_names)
            transaction_ok = _transaction_check(connection)
    except Exception as exc:
        return _result(
            database_ready=False,
            issues=[f"Database readiness check failed: {exc}"],
            instructions=["Confirm the database is reachable and run alembic upgrade head."],
            database_url_present=database_url_present,
            database_mode="missing",
        )

    issues: list[str] = []
    instructions: list[str] = []
    if missing_tables:
        issues.append(f"Missing expected tables: {', '.join(missing_tables)}")
        instructions.append("Run alembic upgrade head from the backend directory.")
    missing_indexes = [
        f"{table}.{hint}"
        for table, report in index_report.items()
        for hint, present in report.items()
        if not present
    ]
    if missing_indexes:
        issues.append(f"Some expected index hints were not found: {', '.join(missing_indexes)}")
        instructions.append("Review migrations 0004 through 0006 and database-schema.sql.")
    if not transaction_ok:
        issues.append("Test transaction could not be created and rolled back.")
        instructions.append("Check database permissions for the app user.")

    return {
        "database_mode": database_mode,
        "database_url_present": database_url_present,
        "connection_ok": True,
        "database_ready": not missing_tables and transaction_ok,
        "postgresql_ready": database_mode == "postgresql" and not missing_tables and transaction_ok,
        "sqlite_testing_fallback": database_mode == "sqlite_testing_fallback" and not missing_tables and transaction_ok,
        "production_like_testing": database_mode == "postgresql" and not missing_tables and transaction_ok,
        "manual_ui_testing_ready": not missing_tables and transaction_ok,
        "ready_for_validation_testing": not missing_tables and transaction_ok,
        "current_revision": current_revision,
        "alembic_current_revision": current_revision,
        "alembic_head_revision": head_revision,
        "validation_cases_table": expected_tables.get("validation_cases", False),
        "validation_benchmark_results_table": expected_tables.get("validation_benchmark_results", False),
        "expected_tables": expected_tables,
        "missing_tables": missing_tables,
        "index_report": index_report,
        "transaction_check": transaction_ok,
        "issues": issues,
        "instructions": instructions,
    }


def _current_revision(connection) -> str | None:
    try:
        return MigrationContext.configure(connection).get_current_revision()
    except Exception:
        return None


def _head_revision() -> str | None:
    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        script = ScriptDirectory.from_config(config)
        return script.get_current_head()
    except Exception:
        return None


def _index_report(inspector, table_names: set[str]) -> dict[str, dict[str, bool]]:
    report: dict[str, dict[str, bool]] = {}
    for table, hints in EXPECTED_INDEX_HINTS.items():
        if table not in table_names:
            report[table] = {hint: False for hint in hints}
            continue
        indexes = inspector.get_indexes(table)
        joined = " ".join(
            [index.get("name") or "" for index in indexes]
            + [" ".join(index.get("column_names") or []) for index in indexes]
        ).lower()
        report[table] = {hint: hint.lower() in joined for hint in hints}
    return report


def _transaction_check(connection) -> bool:
    connection.rollback()
    transaction = connection.begin()
    try:
        connection.execute(text("SELECT 1"))
        transaction.rollback()
        return True
    except Exception:
        transaction.rollback()
        return False


def _result(
    database_ready: bool,
    issues: list[str],
    instructions: list[str],
    database_url_present: bool = False,
    database_mode: str = "missing",
) -> dict[str, Any]:
    return {
        "database_mode": database_mode,
        "database_url_present": database_url_present,
        "connection_ok": False,
        "database_ready": database_ready,
        "postgresql_ready": False,
        "sqlite_testing_fallback": False,
        "production_like_testing": False,
        "manual_ui_testing_ready": False,
        "ready_for_validation_testing": False,
        "current_revision": None,
        "alembic_current_revision": None,
        "alembic_head_revision": _head_revision(),
        "validation_cases_table": False,
        "validation_benchmark_results_table": False,
        "expected_tables": {table: False for table in EXPECTED_TABLES},
        "missing_tables": EXPECTED_TABLES,
        "index_report": {},
        "transaction_check": False,
        "issues": issues,
        "instructions": instructions,
    }


def _with_connect_timeout(database_url: str) -> str:
    if "postgresql" not in database_url or "connect_timeout=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}connect_timeout=5"


def _database_mode(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        return "sqlite_testing_fallback"
    if database_url.startswith("postgresql"):
        return "postgresql"
    return "missing"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify database migration readiness.")
    parser.add_argument("--database-url", default=None, help="Optional database URL override.")
    args = parser.parse_args()
    print(json.dumps(verify_database_readiness(args.database_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

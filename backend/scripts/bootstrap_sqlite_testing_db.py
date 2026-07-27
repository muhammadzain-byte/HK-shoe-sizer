from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base  # noqa: E402
import app.models  # noqa: F401,E402


DEFAULT_SQLITE_URL = f"sqlite:///{(PROJECT_ROOT / 'runtime' / 'local_testing.db').as_posix()}"
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


def bootstrap_sqlite_testing_db(database_url: str | None = None) -> dict[str, Any]:
    database_url = database_url or os.environ.get("DATABASE_URL") or DEFAULT_SQLITE_URL
    if not database_url.startswith("sqlite"):
        return {
            "database_mode": "postgresql",
            "sqlite_testing_fallback": False,
            "ready": False,
            "issues": ["Refusing to bootstrap SQLite fallback because DATABASE_URL is not sqlite."],
        }

    db_path = _sqlite_path(database_url)
    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names())
    except Exception as exc:
        return {
            "database_mode": "sqlite_testing_fallback",
            "sqlite_testing_fallback": True,
            "ready": False,
            "issues": [f"SQLite fallback bootstrap failed: {exc}"],
        }

    missing = [table for table in EXPECTED_TABLES if table not in tables]
    return {
        "database_mode": "sqlite_testing_fallback",
        "sqlite_testing_fallback": True,
        "database_path": str(db_path) if db_path else database_url,
        "ready": not missing,
        "expected_tables": {table: table in tables for table in EXPECTED_TABLES},
        "missing_tables": missing,
        "issues": [f"Missing tables: {', '.join(missing)}"] if missing else [],
        "warning": "SQLite fallback is for local UI testing only, not production accuracy evidence.",
    }


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url.removeprefix(prefix)
    return Path(raw).resolve()


def main() -> int:
    report = bootstrap_sqlite_testing_db()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())

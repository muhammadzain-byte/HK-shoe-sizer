from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REQUIRED_TABLES = [
    "users",
    "foot_scans",
    "uploaded_images",
    "validation_cases",
    "validation_benchmark_results",
]


def verify_validation_tables(database_url: str | None = None) -> dict:
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        return {
            "database_mode": "missing",
            "database_connected": False,
            "tables": {table: False for table in REQUIRED_TABLES},
            "all_required_tables_exist": False,
            "issues": ["DATABASE_URL is not set."],
        }
    try:
        engine = create_engine(_with_connect_timeout(database_url), future=True)
        with engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names())
    except Exception as exc:
        return {
            "database_mode": "missing",
            "database_connected": False,
            "tables": {table: False for table in REQUIRED_TABLES},
            "all_required_tables_exist": False,
            "issues": [f"Database connection failed: {exc}"],
        }
    tables = {table: table in table_names for table in REQUIRED_TABLES}
    missing = [table for table, exists in tables.items() if not exists]
    return {
        "database_mode": "sqlite_testing_fallback" if database_url.startswith("sqlite") else "postgresql",
        "database_connected": True,
        "tables": tables,
        "all_required_tables_exist": not missing,
        "issues": [f"Missing tables: {', '.join(missing)}"] if missing else [],
    }


def _with_connect_timeout(database_url: str) -> str:
    if "postgresql" not in database_url or "connect_timeout=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}connect_timeout=5"


def main() -> int:
    report = verify_validation_tables()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_required_tables_exist"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

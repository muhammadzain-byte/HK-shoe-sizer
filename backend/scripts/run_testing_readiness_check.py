from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def run_testing_readiness_check() -> dict[str, Any]:
    preflight = _run("scripts.system_setup_preflight", "system_setup_preflight")
    audit = _run("scripts.audit_testing_readiness", "audit_testing_readiness")
    database = (
        _run("scripts.verify_database_readiness", "verify_database_readiness")
        if os.environ.get("DATABASE_URL")
        else {"ready_for_validation_testing": False, "issues": ["DATABASE_URL is not set."]}
    )
    tables = (
        _run("scripts.verify_validation_tables", "verify_validation_tables")
        if os.environ.get("DATABASE_URL")
        else {"all_required_tables_exist": False, "issues": ["DATABASE_URL is not set."]}
    )
    smoke = (
        _run("scripts.smoke_test_validation_flow", "smoke_test_validation_flow")
        if database.get("ready_for_validation_testing")
        else {"ready_for_manual_real_device_testing": False, "benchmark_blocker": "Database is not ready."}
    )
    local_upload = _run("scripts.smoke_test_local_upload", "smoke_test_local_upload")
    backend_health = _run("scripts.check_backend_health", "check_backend_health")
    frontend_page = _run("scripts.check_frontend_validation_page", "check_frontend_validation_page")
    report = _run("scripts.export_testing_report", "export_testing_report")
    issues = []
    for payload in (preflight, audit, database, tables, smoke, local_upload, backend_health, frontend_page, report):
        issues.extend(payload.get("issues", []))
    if smoke.get("benchmark_blocker") and not smoke.get("ready_for_manual_real_device_testing"):
        issues.append(smoke["benchmark_blocker"])
    return {
        "end_to_end_testing_ready": bool(
            audit.get("validation_cockpit_ready")
            and database.get("ready_for_validation_testing")
            and tables.get("all_required_tables_exist")
            and smoke.get("ready_for_manual_real_device_testing")
            and local_upload.get("local_storage_ready")
            and local_upload.get("file_saved")
        ),
        "database_ready": bool(database.get("ready_for_validation_testing")),
        "migrations_applied": bool(database.get("ready_for_validation_testing")),
        "validation_tables_live": bool(tables.get("all_required_tables_exist")),
        "validation_api_smoke_passed": bool(smoke.get("ready_for_manual_real_device_testing")),
        "frontend_build_ready": (audit.get("frontend_ready") is True),
        "validation_api_ready": (audit.get("validation_cockpit_ready") is True),
        "local_upload_ready": bool(local_upload.get("local_storage_ready") and local_upload.get("file_saved")),
        "backend_health_ok": backend_health.get("backend_health_ok", False),
        "backend_health_status": backend_health.get("status", "not_running"),
        "frontend_validation_page_ok": frontend_page.get("frontend_validation_page_ok", False),
        "frontend_validation_page_status": frontend_page.get("status", "not_running"),
        "manual_real_device_testing_ready": bool(smoke.get("ready_for_manual_real_device_testing")),
        "issues": issues,
        "next_commands": [
            "docker compose -f infrastructure\\docker-compose.testing.yml up -d",
            "$env:DATABASE_URL=\"postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size\"",
            "cd backend",
            "python scripts\\apply_migrations.py",
            "python scripts\\verify_database_readiness.py",
            "python scripts\\smoke_test_validation_flow.py",
        ],
        "commands_to_run_next": [
            "powershell -ExecutionPolicy Bypass -File scripts\\setup-local-testing-db.ps1",
            ".\\scripts\\start-testing-backend.ps1",
            ".\\scripts\\start-testing-frontend.ps1",
        ],
    }


def _run(module_name: str, function_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        return getattr(module, function_name)()
    except Exception as exc:
        return {"issues": [f"{module_name}.{function_name} failed: {exc}"]}


def main() -> int:
    result = run_testing_readiness_check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def system_setup_preflight() -> dict[str, Any]:
    database_url = os.environ.get("DATABASE_URL")
    docker_available = shutil.which("docker") is not None
    docker_compose_available = _command_ok(["docker", "compose", "version"]) if docker_available else False
    report = {
        "windows_version": platform.platform(),
        "powershell_available": shutil.which("powershell") is not None,
        "python_version": _command_output([sys.executable, "--version"]),
        "pip_version": _command_output([sys.executable, "-m", "pip", "--version"]),
        "node_version": _command_output(["node", "--version"]),
        "npm_version": _command_output(["npm", "--version"]),
        "docker_available": docker_available,
        "docker_compose_available": docker_compose_available,
        "postgres_client_available": shutil.which("psql") is not None,
        "winget_available": shutil.which("winget") is not None,
        "project_root": str(PROJECT_ROOT),
        "backend_folder_exists": (PROJECT_ROOT / "backend").exists(),
        "frontend_folder_exists": (PROJECT_ROOT / "frontend").exists(),
        "backend_env_exists": (PROJECT_ROOT / "backend" / ".env").exists(),
        "backend_env_testing_exists": (PROJECT_ROOT / "backend" / ".env.testing").exists(),
        "frontend_env_exists": (PROJECT_ROOT / "frontend" / ".env").exists(),
        "database_url_present": bool(database_url),
        "database_url_masked": _mask_database_url(database_url),
        "python_ok": True,
        "node_ok": shutil.which("node") is not None,
        "npm_ok": shutil.which("npm") is not None,
        "issues": [],
        "next_steps": [],
    }
    if not report["node_ok"]:
        report["issues"].append("Node.js is not available.")
    if not report["npm_ok"]:
        report["issues"].append("npm is not available.")
    if not docker_available:
        report["issues"].append("Docker is not available on PATH.")
        report["next_steps"].append("Run scripts\\setup-local-testing-db.ps1 to try Docker/PostgreSQL setup.")
    if not report["postgres_client_available"]:
        report["next_steps"].append("Install PostgreSQL client tools or use Docker PostgreSQL.")
    if not database_url:
        report["next_steps"].append("Set DATABASE_URL for the local testing database.")
    return report


def _command_ok(command: list[str]) -> bool:
    return subprocess.run(command, capture_output=True, text=True, check=False).returncode == 0


def _command_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr) else None


def _mask_database_url(value: str | None) -> str | None:
    if not value:
        return None
    if "@" not in value or ":" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    if ":" not in prefix:
        return value
    user_part = prefix.split("//", 1)[-1].split(":", 1)[0]
    scheme = prefix.split("//", 1)[0] + "//" if "//" in prefix else ""
    return f"{scheme}{user_part}:***@{suffix}"


def main() -> int:
    print(json.dumps(system_setup_preflight(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

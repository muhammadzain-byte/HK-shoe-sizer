from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_DATABASE_URL = "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_EMAIL = "localtest@example.com"
DEFAULT_PASSWORD = "TestPassword123!"


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 20,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="ignore")
            return response.status, json.loads(response_body) if response_body else {}
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            payload = {"detail": response_body}
        return exc.code, payload


def _database_connected(database_url: str) -> tuple[bool, str | None]:
    try:
        engine = create_engine(database_url, future=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def smoke_test_auth_flow(
    api_base_url: str = DEFAULT_API_BASE_URL,
    database_url: str | None = None,
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "backend_auth_ready": False,
        "database_connected": False,
        "register_ok": False,
        "login_ok": False,
        "token_received": False,
        "me_ok": False,
        "test_email": email,
        "issues": [],
    }
    database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    db_connected, db_error = _database_connected(database_url)
    report["database_connected"] = db_connected
    if db_error:
        report["issues"].append(f"Database connection failed: {db_error}")
        return report

    try:
        status, payload = _request_json(
            "POST",
            f"{api_base_url}/auth/register",
            {
                "email": email,
                "password": password,
                "first_name": "Local",
                "last_name": "Tester",
            },
        )
        if status in {201, 409}:
            report["register_ok"] = True
        else:
            report["issues"].append(f"Register returned {status}: {payload}")

        status, payload = _request_json(
            "POST",
            f"{api_base_url}/auth/login",
            {"email": email, "password": password},
        )
        token = payload.get("access_token") if isinstance(payload, dict) else None
        report["login_ok"] = status == 200
        report["token_received"] = bool(token)
        if status != 200 or not token:
            report["issues"].append(f"Login returned {status}: {payload}")
            return report

        status, payload = _request_json("GET", f"{api_base_url}/auth/me", token=token)
        report["me_ok"] = status == 200 and payload.get("email") == email
        if not report["me_ok"]:
            report["issues"].append(f"Auth me returned {status}: {payload}")
    except (OSError, TimeoutError, URLError) as exc:
        report["issues"].append(f"Backend auth endpoint is unreachable: {exc}")

    report["backend_auth_ready"] = all(
        [
            report["database_connected"],
            report["register_ok"],
            report["login_ok"],
            report["token_received"],
            report["me_ok"],
        ]
    )
    return report


def main() -> int:
    report = smoke_test_auth_flow()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["backend_auth_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

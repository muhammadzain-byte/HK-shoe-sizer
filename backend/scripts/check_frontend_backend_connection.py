from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_FRONTEND_ORIGIN = "http://localhost:3000"
RUNTIME_FILE = PROJECT_ROOT / "runtime" / "local-stack.json"


def _fetch(url: str, timeout: int = 5) -> tuple[bool, int | None, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(1200).decode("utf-8", errors="ignore")
            return True, response.status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return False, exc.code, body
    except (OSError, TimeoutError, URLError) as exc:
        return False, None, str(exc)


def _cors_preflight(
    url: str,
    method: str,
    origin: str = DEFAULT_FRONTEND_ORIGIN,
    timeout: int = 5,
) -> tuple[bool, int | None, str]:
    request = Request(
        url,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        method="OPTIONS",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300, response.status, response.read().decode()
    except HTTPError as exc:
        return False, exc.code, exc.read().decode("utf-8", errors="ignore")
    except (OSError, TimeoutError, URLError) as exc:
        return False, None, str(exc)


def _env_local_api_base() -> str | None:
    env_file = PROJECT_ROOT / "frontend" / ".env.local"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        clean_line = line.lstrip("\ufeff")
        if clean_line.startswith("NEXT_PUBLIC_API_BASE_URL="):
            return clean_line.split("=", 1)[1].strip()
    return None


def check_frontend_backend_connection(
    api_base_url: str | None = None,
    frontend_origin: str | None = None,
) -> dict:
    runtime = _runtime()
    api_base_url = api_base_url or runtime.get("api_base_url", DEFAULT_API_BASE_URL)
    frontend_origin = frontend_origin or runtime.get("frontend_url", DEFAULT_FRONTEND_ORIGIN)
    issues: list[str] = []
    next_steps: list[str] = []

    health_ok, health_status, health_body = _fetch(f"{api_base_url}/health")
    backend_health_ok = health_ok and health_status == 200 and '"status":"ok"' in health_body.replace(" ", "")
    if not backend_health_ok:
        issues.append(f"Backend health is not reachable at {api_base_url}/health.")
        next_steps.append("Run .\\scripts\\run-app-now.ps1 -Force.")

    register_ok, register_status, register_body = (
        _cors_preflight(f"{api_base_url}/auth/register", "POST", frontend_origin)
        if backend_health_ok
        else (False, None, "backend health failed")
    )
    login_ok, login_status, login_body = (
        _cors_preflight(f"{api_base_url}/auth/login", "POST", frontend_origin)
        if backend_health_ok
        else (False, None, "backend health failed")
    )
    auth_endpoints_reachable = register_ok and login_ok
    if not auth_endpoints_reachable:
        issues.append(
            "Auth endpoint CORS preflight failed: "
            f"register={register_status} {register_body}; login={login_status} {login_body}"
        )
        next_steps.append(f"Verify CORS_ORIGINS includes {frontend_origin}.")

    login_page_ok, login_page_status, login_body = _fetch(f"{frontend_origin}/login")
    register_page_ok, register_page_status, register_page_body = _fetch(f"{frontend_origin}/register")
    new_scan_page_ok, new_scan_page_status, new_scan_body = _fetch(f"{frontend_origin}/scans/new")
    validation_page_ok, validation_page_status, validation_body = _fetch(f"{frontend_origin}/validation")
    frontend_login_page_ok = login_page_ok and login_page_status == 200 and "<html" in login_body.lower()
    frontend_register_page_ok = (
        register_page_ok and register_page_status == 200 and "<html" in register_page_body.lower()
    )
    frontend_validation_page_ok = (
        validation_page_ok and validation_page_status == 200 and "<html" in validation_body.lower()
    )
    frontend_new_scan_page_ok = (
        new_scan_page_ok and new_scan_page_status == 200 and "<html" in new_scan_body.lower()
    )
    if not frontend_login_page_ok or not frontend_register_page_ok or not frontend_new_scan_page_ok:
        issues.append("Frontend login/register/new-scan pages are not reachable.")
        next_steps.append("Run .\\scripts\\run-app-now.ps1 -Force.")

    env_local_api_base = _env_local_api_base()
    if env_local_api_base != api_base_url:
        issues.append("frontend\\.env.local does not define the expected API base URL.")
        next_steps.append(f"Set NEXT_PUBLIC_API_BASE_URL={api_base_url} and restart frontend.")

    return {
        "backend_health_ok": backend_health_ok,
        "auth_endpoints_reachable": auth_endpoints_reachable,
        "frontend_login_page_ok": frontend_login_page_ok,
        "frontend_register_page_ok": frontend_register_page_ok,
        "frontend_new_scan_page_ok": frontend_new_scan_page_ok,
        "frontend_validation_page_ok": frontend_validation_page_ok,
        "frontend_api_base_expected": api_base_url,
        "frontend_api_base_configured": env_local_api_base,
        "issues": issues,
        "next_steps": next_steps,
    }


def _runtime() -> dict:
    if not RUNTIME_FILE.exists():
        return {}
    try:
        return json.loads(RUNTIME_FILE.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    report = check_frontend_backend_connection()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

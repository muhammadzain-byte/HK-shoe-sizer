from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.create_dev_user import DEV_EMAIL, DEV_PASSWORD  # noqa: E402
from scripts.smoke_test_new_scan_flow import _bad_test_image_bytes, _request_json, _upload_image  # noqa: E402

RUNTIME_FILE = PROJECT_ROOT / "runtime" / "local-stack.json"


def _fetch(url: str, timeout: int = 10) -> tuple[bool, int | None, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(2000).decode("utf-8", errors="ignore")
            return True, response.status, body
    except HTTPError as exc:
        return False, exc.code, exc.read().decode("utf-8", errors="ignore")
    except (OSError, TimeoutError, URLError) as exc:
        return False, None, str(exc)


def _runtime() -> dict[str, Any]:
    if not RUNTIME_FILE.exists():
        return {
            "api_base_url": "http://localhost:8000/api/v1",
            "frontend_url": "http://localhost:3000",
            "health_url": "http://localhost:8000/api/v1/health",
            "database_url": None,
        }
    return json.loads(RUNTIME_FILE.read_text(encoding="utf-8-sig"))


def check_live_app_access() -> dict[str, Any]:
    runtime = _runtime()
    api_base = runtime["api_base_url"]
    frontend = runtime["frontend_url"].rstrip("/")
    health_url = runtime["health_url"]

    health_ok, health_status, health_body = _fetch(health_url)
    frontend_ok, frontend_status, frontend_body = _fetch(frontend)
    login_ok, login_status, login_body = _fetch(f"{frontend}/login")
    register_ok, register_status, register_body = _fetch(f"{frontend}/register")
    new_scan_ok, new_scan_status, new_scan_body = _fetch(f"{frontend}/scans/new")
    validation_ok, validation_status, validation_body = _fetch(f"{frontend}/validation")

    auth_status, auth_payload = _request_json(
        "POST",
        f"{api_base}/auth/login",
        {"email": DEV_EMAIL, "password": DEV_PASSWORD},
        timeout=30,
    )
    auth_smoke_ok = auth_status == 200 and bool(auth_payload.get("access_token"))
    new_scan = _http_new_scan_smoke(api_base, auth_payload.get("access_token") if auth_smoke_ok else None)

    report = {
        "backend_health_ok": health_ok and health_status == 200 and '"status":"ok"' in health_body.replace(" ", ""),
        "frontend_ok": frontend_ok and frontend_status == 200 and "<html" in frontend_body.lower(),
        "login_page_ok": login_ok and login_status == 200 and "<html" in login_body.lower(),
        "register_page_ok": register_ok and register_status == 200 and "<html" in register_body.lower(),
        "new_scan_page_ok": new_scan_ok and new_scan_status == 200 and "<html" in new_scan_body.lower(),
        "validation_page_ok": validation_ok and validation_status == 200 and "<html" in validation_body.lower(),
        "auth_smoke_ok": auth_smoke_ok,
        "new_scan_smoke_ok": bool(new_scan.get("scan_created") and new_scan.get("bad_image_rejected_safely")),
        "local_upload_ok": bool(new_scan.get("local_upload_ok")),
        "database_mode": runtime.get("database_mode"),
        "urls": {
            "backend_health": health_url,
            "frontend": frontend,
            "login": f"{frontend}/login",
            "register": f"{frontend}/register",
            "new_scan": f"{frontend}/scans/new",
            "validation": f"{frontend}/validation",
        },
        "new_scan_smoke": new_scan,
        "issues": [],
    }
    for key in [
        "backend_health_ok",
        "frontend_ok",
        "login_page_ok",
        "register_page_ok",
        "new_scan_page_ok",
        "validation_page_ok",
        "auth_smoke_ok",
        "new_scan_smoke_ok",
        "local_upload_ok",
    ]:
        if not report[key]:
            report["issues"].append(f"{key} is false.")
    report["app_access_ready"] = not report["issues"]
    return report


def _http_new_scan_smoke(api_base: str, token: str | None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "scan_created": False,
        "local_upload_ok": False,
        "quality_check_returned": False,
        "bad_image_rejected_safely": False,
        "issues": [],
    }
    if not token:
        report["issues"].append("Auth token missing; cannot run new scan smoke.")
        return report
    try:
        status, scan = _request_json(
            "POST",
            f"{api_base}/scans",
            {"foot_side": "right"},
            token=token,
            timeout=30,
        )
        scan_id = scan.get("id")
        report["scan_created"] = status == 201 and bool(scan_id)
        if not report["scan_created"]:
            report["issues"].append(f"Scan creation failed: {status} {scan}")
            return report

        status, upload = _upload_image(
            f"{api_base}/uploads/local",
            _bad_test_image_bytes(),
            scan_id,
            token,
            timeout=30,
        )
        image_id = upload.get("image_id")
        report["local_upload_ok"] = status == 201 and bool(image_id)
        if not report["local_upload_ok"]:
            report["issues"].append(f"Local upload failed: {status} {upload}")
            return report

        status, quality = _request_json(
            "POST",
            f"{api_base}/ai/scans/{scan_id}/capture-quality",
            {"uploaded_image_id": image_id},
            token=token,
            timeout=45,
        )
        report["quality_check_returned"] = status == 200 and "capture_status" in quality
        report["bad_image_rejected_safely"] = (
            report["quality_check_returned"]
            and quality.get("capture_status") in {"reject", "needs_adjustment"}
            and bool(quality.get("issues") or quality.get("instructions"))
        )
        if not report["bad_image_rejected_safely"]:
            report["issues"].append(f"Bad image was not rejected safely: {status} {quality}")
    except Exception as exc:
        report["issues"].append(f"HTTP new scan smoke failed: {exc}")
    return report


def main() -> int:
    report = check_live_app_access()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["app_access_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

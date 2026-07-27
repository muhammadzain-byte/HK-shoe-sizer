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
            return True, response.status, response.read(2000).decode("utf-8", errors="ignore")
    except HTTPError as exc:
        return False, exc.code, exc.read().decode("utf-8", errors="ignore")
    except (OSError, TimeoutError, URLError) as exc:
        return False, None, str(exc)


def _runtime() -> tuple[bool, dict[str, Any]]:
    if not RUNTIME_FILE.exists():
        return False, {}
    try:
        return True, json.loads(RUNTIME_FILE.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return False, {}


def debug_live_scan_runtime() -> dict[str, Any]:
    runtime_loaded, runtime = _runtime()
    api_base = runtime.get("api_base_url", "http://localhost:8000/api/v1")
    health_url = runtime.get("health_url", f"{api_base}/health")
    frontend_new_scan_url = runtime.get("new_scan_url", "http://localhost:3000/scans/new")
    report: dict[str, Any] = {
        "runtime_loaded": runtime_loaded,
        "backend_health_ok": False,
        "database_mode": "unknown",
        "auth_ok": False,
        "auth_me_ok": False,
        "scan_create_ok": False,
        "local_upload_ok": False,
        "capture_quality_safe_response": False,
        "frontend_new_scan_ok": False,
        "ready_for_browser_scan_test": False,
        "issues": [],
    }

    health_ok, health_status, health_body = _fetch(health_url)
    if health_ok and health_status == 200:
        try:
            health = json.loads(health_body)
        except json.JSONDecodeError:
            health = {}
        report["backend_health_ok"] = health.get("status") == "ok"
        report["database_mode"] = health.get("database_mode", health.get("database", "unknown"))
    if not report["backend_health_ok"]:
        report["issues"].append(f"Backend health failed at {health_url}: {health_status} {health_body}")
        return report

    status, login = _request_json(
        "POST",
        f"{api_base}/auth/login",
        {"email": DEV_EMAIL, "password": DEV_PASSWORD},
        timeout=30,
    )
    token = login.get("access_token")
    report["auth_ok"] = status == 200 and bool(token)
    if not report["auth_ok"]:
        report["issues"].append(f"Auth login failed: {status} {login}")
        return report

    status, me = _request_json("GET", f"{api_base}/auth/me", token=token, timeout=30)
    report["auth_me_ok"] = status == 200 and me.get("email") == DEV_EMAIL
    if not report["auth_me_ok"]:
        report["issues"].append(f"Auth me failed: {status} {me}")

    status, scan = _request_json(
        "POST",
        f"{api_base}/scans",
        {"foot_side": "right"},
        token=token,
        timeout=30,
    )
    scan_id = scan.get("id")
    report["scan_create_ok"] = status == 201 and bool(scan_id)
    if not report["scan_create_ok"]:
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
    report["capture_quality_safe_response"] = (
        status == 200
        and quality.get("capture_status") in {"reject", "needs_adjustment", "ready"}
        and (quality.get("capture_status") == "ready" or bool(quality.get("instructions") or quality.get("issues")))
    )
    if not report["capture_quality_safe_response"]:
        report["issues"].append(f"Capture quality response was unsafe: {status} {quality}")

    page_ok, page_status, page_body = _fetch(frontend_new_scan_url, timeout=20)
    report["frontend_new_scan_ok"] = page_ok and page_status == 200 and "<html" in page_body.lower()
    if not report["frontend_new_scan_ok"]:
        report["issues"].append(f"Frontend new scan page failed: {page_status} {page_body[:300]}")

    report["ready_for_browser_scan_test"] = all(
        bool(report[key])
        for key in [
            "runtime_loaded",
            "backend_health_ok",
            "auth_ok",
            "auth_me_ok",
            "scan_create_ok",
            "local_upload_ok",
            "capture_quality_safe_response",
            "frontend_new_scan_ok",
        ]
    )
    return report


def main() -> int:
    report = debug_live_scan_runtime()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_browser_scan_test"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

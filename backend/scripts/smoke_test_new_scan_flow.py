from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.create_dev_user import DEV_EMAIL, DEV_PASSWORD, create_dev_user  # noqa: E402
from scripts.verify_database_readiness import verify_database_readiness  # noqa: E402

DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_DATABASE_URL = "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
RUNTIME_FILE = BACKEND_DIR.parent / "runtime" / "local-stack.json"


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 120,
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
            return exc.code, json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            return exc.code, {"detail": response_body}


def _upload_image(
    url: str,
    image_bytes: bytes,
    foot_scan_id: str,
    token: str,
    timeout: int = 120,
) -> tuple[int, dict[str, Any]]:
    boundary = "----mirrorstep-local-smoke-boundary"
    parts = [
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="foot_scan_id"\r\n\r\n'
        f"{foot_scan_id}\r\n",
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="bad-smoke.png"\r\n'
        "Content-Type: image/png\r\n\r\n",
    ]
    body = b"".join(part.encode("utf-8") for part in parts)
    body += image_bytes
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="ignore")
            return response.status, json.loads(response_body) if response_body else {}
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="ignore")
        try:
            return exc.code, json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            return exc.code, {"detail": response_body}


def _bad_test_image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 240), color=(235, 235, 235)).save(output, format="PNG")
    return output.getvalue()


def smoke_test_new_scan_flow(
    api_base_url: str = DEFAULT_API_BASE_URL,
    database_url: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "db_ready": False,
        "auth_ready": False,
        "scan_created": False,
        "local_upload_ok": False,
        "image_linked_to_scan": False,
        "quality_check_returned": False,
        "bad_image_rejected_safely": False,
        "scan_readable": False,
        "ready_for_real_scan_testing": False,
        "issues": [],
    }
    database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    db_report = verify_database_readiness(database_url)
    report["db_ready"] = bool(db_report.get("database_ready"))
    if not report["db_ready"]:
        report["issues"].append(f"Database is not ready: {db_report.get('issues')}")
        return report

    dev_user = create_dev_user()
    if not dev_user.get("dev_user_ready"):
        report["issues"].append(f"Dev user is not ready: {dev_user.get('issues')}")
        return report

    try:
        status, payload = _request_json(
            "POST",
            f"{api_base_url}/auth/login",
            {"email": DEV_EMAIL, "password": DEV_PASSWORD},
        )
        token = payload.get("access_token")
        report["auth_ready"] = status == 200 and bool(token)
        if not report["auth_ready"]:
            report["issues"].append(f"Login failed: {status} {payload}")
            return report

        status, scan = _request_json(
            "POST",
            f"{api_base_url}/scans",
            {"foot_side": "right"},
            token=token,
        )
        scan_id = scan.get("id")
        report["scan_created"] = status == 201 and bool(scan_id)
        if not report["scan_created"]:
            report["issues"].append(f"Scan creation failed: {status} {scan}")
            return report

        status, upload = _upload_image(
            f"{api_base_url}/uploads/local",
            _bad_test_image_bytes(),
            scan_id,
            token,
        )
        image_id = upload.get("image_id")
        report["local_upload_ok"] = status == 201 and bool(image_id)
        if not report["local_upload_ok"]:
            report["issues"].append(f"Local upload failed: {status} {upload}")
            return report

        status, detail = _request_json("GET", f"{api_base_url}/scans/{scan_id}", token=token)
        uploads = detail.get("uploaded_images") or []
        report["scan_readable"] = status == 200
        report["image_linked_to_scan"] = any(str(item.get("id")) == str(image_id) for item in uploads)

        status, quality = _request_json(
            "POST",
            f"{api_base_url}/ai/scans/{scan_id}/capture-quality",
            {"uploaded_image_id": image_id},
            token=token,
        )
        report["quality_check_returned"] = status == 200 and "capture_status" in quality
        report["bad_image_rejected_safely"] = (
            report["quality_check_returned"]
            and quality.get("capture_status") in {"reject", "needs_adjustment"}
            and bool(quality.get("issues") or quality.get("instructions"))
        )
        if not report["bad_image_rejected_safely"]:
            report["issues"].append(f"Bad image was not rejected safely: {status} {quality}")
    except (OSError, TimeoutError, URLError) as exc:
        report["issues"].append(f"New scan smoke test could not reach backend: {exc}")

    report["ready_for_real_scan_testing"] = all(
        [
            report["db_ready"],
            report["auth_ready"],
            report["scan_created"],
            report["local_upload_ok"],
            report["image_linked_to_scan"],
            report["quality_check_returned"],
            report["bad_image_rejected_safely"],
            report["scan_readable"],
        ]
    )
    return report


def main() -> int:
    api_base_url = DEFAULT_API_BASE_URL
    database_url = None
    if RUNTIME_FILE.exists():
        runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8-sig"))
        api_base_url = runtime.get("api_base_url", api_base_url)
        database_url = runtime.get("database_url")
    report = smoke_test_new_scan_flow(api_base_url=api_base_url, database_url=database_url)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_real_scan_testing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

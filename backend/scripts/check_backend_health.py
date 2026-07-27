from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import urlopen


def check_backend_health(url: str = "http://localhost:8000/api/v1/health") -> dict:
    try:
        with urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8")
    except (OSError, TimeoutError, URLError) as exc:
        return {
            "backend_health_ok": False,
            "status": "not_running",
            "url": url,
            "issues": [str(exc)],
            "next_steps": ["Run .\\scripts\\restart-local-testing-stack.ps1 -Force"],
        }
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {"raw": body[:200]}
    required_ok = (
        payload.get("status") == "ok"
        and payload.get("database") == "connected"
        and payload.get("validation_tables") is True
        and payload.get("auth_ready") is True
        and payload.get("local_upload_ready") is True
    )
    issues = [] if required_ok else payload.get("issues", ["Backend health is not fully ready."])
    return {
        "backend_health_ok": required_ok,
        "status": "ok" if required_ok else "not_ready",
        "url": url,
        "payload": payload,
        "issues": issues,
        "next_steps": [] if required_ok else ["Run .\\scripts\\restart-local-testing-stack.ps1 -Force"],
    }


def main() -> int:
    report = check_backend_health()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["backend_health_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

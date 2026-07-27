from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import urlopen


def check_frontend_validation_page(url: str = "http://localhost:3000/validation") -> dict:
    try:
        with urlopen(url, timeout=20) as response:
            body = response.read(1000).decode("utf-8", errors="ignore")
    except (OSError, TimeoutError, URLError) as exc:
        return {
            "frontend_validation_page_ok": False,
            "status": "not_running",
            "url": url,
            "issues": [str(exc)],
            "next_steps": ["Run .\\scripts\\restart-local-testing-stack.ps1 -Force"],
        }
    ok = "<html" in body.lower() or "__next" in body.lower()
    return {
        "frontend_validation_page_ok": ok,
        "status": "ok" if ok else "unexpected_response",
        "url": url,
        "issues": [] if ok else ["Validation page did not return expected HTML."],
        "next_steps": [] if ok else ["Run .\\scripts\\restart-local-testing-stack.ps1 -Force"],
    }


def main() -> int:
    report = check_frontend_validation_page()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["frontend_validation_page_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

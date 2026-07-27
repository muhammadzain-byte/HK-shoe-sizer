from __future__ import annotations

import json
import socket


def testing_urls() -> dict:
    lan_ip = _lan_ip()
    return {
        "local_backend_url": "http://localhost:8000",
        "local_frontend_url": "http://localhost:3000/validation",
        "lan_backend_url": f"http://{lan_ip}:8000" if lan_ip else None,
        "lan_frontend_url": f"http://{lan_ip}:3000/validation" if lan_ip else None,
        "reminders": [
            "Android/iPhone must be on the same Wi-Fi as this PC for LAN URLs.",
            "Mobile camera access may require HTTPS.",
            "For phone testing, set NEXT_PUBLIC_API_BASE_URL to the LAN or tunnel backend URL before starting frontend.",
            "Safe HTTPS options: desktop upload first, Cloudflare Tunnel/ngrok, or mkcert local HTTPS.",
        ],
    }


def _lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def main() -> int:
    print(json.dumps(testing_urls(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

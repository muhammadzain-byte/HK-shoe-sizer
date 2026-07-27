from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402

DEV_EMAIL = "zaintariq1822@gmail.com"
DEV_PASSWORD = "TestPassword123!"


def create_dev_user(
    email: str = DEV_EMAIL,
    password: str = DEV_PASSWORD,
    first_name: str = "Muhammad Zain",
    last_name: str = "Ul Abdin",
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "dev_user_ready": False,
        "email": email,
        "password_for_local_testing": password,
        "message": "Use this only for local development testing.",
        "created": False,
        "updated": False,
        "issues": [],
    }
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email.lower()))
            if user is None:
                user = User(
                    email=email.lower(),
                    password_hash=hash_password(password),
                    first_name=first_name,
                    last_name=last_name,
                    gender="woman",
                    is_active=True,
                )
                db.add(user)
                report["created"] = True
            else:
                user.password_hash = hash_password(password)
                user.first_name = first_name
                user.last_name = last_name
                user.gender = "woman"
                user.is_active = True
                report["updated"] = True
            db.commit()
            report["dev_user_ready"] = True
    except Exception as exc:
        report["issues"].append(str(exc))
    return report


def main() -> int:
    report = create_dev_user()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["dev_user_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

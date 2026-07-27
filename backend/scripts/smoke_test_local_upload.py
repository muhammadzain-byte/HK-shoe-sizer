from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from PIL import Image
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.uploaded_image import UploadedImage  # noqa: E402
from app.models.user import User  # noqa: E402


def smoke_test_local_upload(storage_dir: str | None = None) -> dict:
    storage_root = Path(storage_dir or settings.local_storage_dir)
    storage_root.mkdir(parents=True, exist_ok=True)
    file_name = f"local-upload-smoke-{uuid4().hex}.png"
    file_path = storage_root / file_name
    Image.new("RGB", (4, 4), color=(240, 240, 240)).save(file_path)
    report = {
        "local_storage_ready": storage_root.exists(),
        "file_saved": file_path.exists(),
        "db_record_created": False,
        "served_url_checked": False,
        "issues": [],
    }
    if not os.environ.get("DATABASE_URL"):
        report["issues"].append("DATABASE_URL is not set; skipped DB record check.")
        return report
    try:
        with SessionLocal() as db:
            created_user = False
            user = db.scalar(select(User).where(User.email == "local-upload-smoke@example.test"))
            if not user:
                user = User(
                    email="local-upload-smoke@example.test",
                    password_hash="smoke-only",
                    gender="woman",
                )
                db.add(user)
                db.flush()
                created_user = True
            image = UploadedImage(
                user_id=user.id,
                bucket="local",
                object_key=file_name,
                content_type="image/png",
                byte_size=file_path.stat().st_size,
                upload_status="uploaded",
            )
            db.add(image)
            db.flush()
            exists = db.scalar(select(UploadedImage).where(UploadedImage.id == image.id)) is not None
            report["db_record_created"] = bool(exists)
            db.delete(image)
            if created_user:
                db.delete(user)
            db.commit()
    except Exception as exc:
        report["issues"].append(f"DB record check failed: {exc}")
    return report


def main() -> int:
    report = smoke_test_local_upload()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["local_storage_ready"] and report["file_saved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

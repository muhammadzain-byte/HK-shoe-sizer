import os
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")

from app.models.uploaded_image import UploadedImage
from app.services.storage.s3_service import S3StorageService


def test_local_storage_reads_file(monkeypatch, tmp_path: Path) -> None:
    file_path = tmp_path / "sample.jpg"
    file_path.write_bytes(b"image-bytes")

    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))

    assert S3StorageService().get_object_bytes("local", "sample.jpg") == b"image-bytes"


def test_uploaded_image_local_record_shape() -> None:
    image = UploadedImage(
        id=uuid4(),
        user_id=uuid4(),
        bucket="local",
        object_key="test.jpg",
        content_type="image/jpeg",
        byte_size=10,
        upload_status="uploaded",
    )

    assert image.bucket == "local"
    assert image.upload_status == "uploaded"

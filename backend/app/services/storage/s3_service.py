from dataclasses import dataclass
from pathlib import Path

import boto3

from app.core.config import settings


@dataclass(frozen=True)
class PresignedUpload:
    upload_url: str
    headers: dict[str, str]
    expires_in_seconds: int


class S3StorageService:
    def __init__(self) -> None:
        self.client = None if settings.storage_backend == "local" else boto3.client("s3", region_name=settings.aws_region)

    def create_presigned_put_url(self, object_key: str, content_type: str) -> PresignedUpload:
        if self.client is None:
            raise RuntimeError("Presigned S3 uploads are unavailable when STORAGE_BACKEND=local.")
        upload_url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.aws_s3_bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.s3_presign_expire_seconds,
        )
        return PresignedUpload(
            upload_url=upload_url,
            headers={"Content-Type": content_type},
            expires_in_seconds=settings.s3_presign_expire_seconds,
        )

    def get_object_bytes(self, bucket: str, object_key: str) -> bytes:
        if bucket == "local" or settings.storage_backend == "local":
            return (Path(settings.local_storage_dir) / object_key).read_bytes()
        if self.client is None:
            raise RuntimeError("S3 client is unavailable.")
        response = self.client.get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read()

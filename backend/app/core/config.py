from functools import cached_property

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = Field(
        "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size",
        validation_alias="DATABASE_URL",
    )
    jwt_secret_key: str = Field("dev-only-change-me", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "women-shoe-sizing-local"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_presign_expire_seconds: int = 900
    cors_allowed_origins_raw: str = Field(
        "http://localhost:3000,http://127.0.0.1:3000",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )
    storage_backend: str = Field("local", validation_alias="STORAGE_BACKEND")
    local_storage_dir: str = Field("storage/uploads", validation_alias="LOCAL_STORAGE_DIR")
    public_upload_base_url: str = Field("http://localhost:8000/uploads", validation_alias="PUBLIC_UPLOAD_BASE_URL")
    enable_research_models: bool = Field(False, validation_alias="ENABLE_RESEARCH_MODELS")
    local_testing_db_fallback: bool = Field(False, validation_alias="LOCAL_TESTING_DB_FALLBACK")
    log_level: str = "INFO"
    sam2_model_id: str = "facebook/sam2.1-hiera-large"
    sam2_device: str = "auto"
    sam2_min_mask_area_ratio: float = 0.025
    sam2_edge_margin_ratio: float = 0.03
    sam2_min_confidence: float = 0.50

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        production = self.app_env.lower() in {"production", "prod"}
        if production and self.jwt_secret_key == "dev-only-change-me":
            raise ValueError("JWT_SECRET_KEY must be set to a strong non-default value in production.")
        if production and any(origin.startswith("http://") for origin in self.cors_allowed_origins):
            raise ValueError("Production CORS origins must use HTTPS.")
        if production and "*" in self.cors_allowed_origins:
            raise ValueError("Wildcard CORS origins are not allowed in production.")
        if production and self.storage_backend == "local":
            raise ValueError("Local public upload storage is not allowed in production.")
        if production and self.local_testing_db_fallback:
            raise ValueError("LOCAL_TESTING_DB_FALLBACK is not allowed in production.")
        if production and not self.database_url.startswith("postgresql"):
            raise ValueError("Production requires a PostgreSQL DATABASE_URL.")
        return self

    @cached_property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins_raw.split(",")
            if origin.strip()
        ]


settings = Settings()

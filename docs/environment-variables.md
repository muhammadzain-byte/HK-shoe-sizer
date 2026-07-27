# Environment Variables

Do not commit real secrets. These values are for local testing only.

## Backend

- `DATABASE_URL`: PostgreSQL connection string.
- `JWT_SECRET_KEY`: Secret used to sign login tokens.
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` / `ACCESS_TOKEN_EXPIRE_MINUTES`: Token lifetime in minutes.
- `CORS_ALLOWED_ORIGINS` / `CORS_ORIGINS`: Frontend origins allowed to call the backend.
- `STORAGE_BACKEND`: Use `local` for testing without S3.
- `LOCAL_STORAGE_DIR`: Local folder for uploaded images.
- `PUBLIC_UPLOAD_BASE_URL`: Public URL for locally served uploads.
- `AWS_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: Cloud storage settings.
- `ENABLE_RESEARCH_MODELS`: Must stay `false` for production-style validation testing.
- `SAM2_MODEL_ID`, `SAM2_DEVICE`: SAM 2 runtime settings.

## Frontend

- `NEXT_PUBLIC_API_BASE_URL`: Backend API URL.
- `NEXT_PUBLIC_BACKEND_ORIGIN`: Backend origin for non-API URLs.
- `NEXT_PUBLIC_APP_NAME`: Display name.
- `NEXT_PUBLIC_ENVIRONMENT`: Local/development label.

# Environment Configuration

## Backend

Copy `backend/.env.example` to `backend/.env` for local development.

Never commit real secrets. In production, prefer AWS IAM roles for S3 access instead of static access keys.

Required values:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `AWS_REGION`
- `AWS_S3_BUCKET`
- `CORS_ALLOWED_ORIGINS`

SAM 2 segmentation values:

- `SAM2_MODEL_ID`
- `SAM2_DEVICE`
- `SAM2_MIN_MASK_AREA_RATIO`
- `SAM2_EDGE_MARGIN_RATIO`
- `SAM2_MIN_CONFIDENCE`

Optional local-only values:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Frontend

Copy `frontend/.env.example` to `frontend/.env.local`.

Required values:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_APP_NAME`
- `NEXT_PUBLIC_ENVIRONMENT`

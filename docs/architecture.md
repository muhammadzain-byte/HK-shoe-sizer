# Women's Shoe Sizing Platform Architecture

## 1. System Architecture

This monorepo is the foundation for a women-only shoe measurement platform inspired by products such as MirrorSize. The current phase focuses on production-ready application structure, service boundaries, authentication, persistence, storage abstraction, and future AI integration contracts. Dataset collection, model training, and real measurement inference are intentionally out of scope.

### High-Level Components

- `frontend/`: Next.js 15 application using TypeScript, Tailwind CSS, and the App Router.
- `backend/`: FastAPI service using Python 3.12, PostgreSQL, JWT authentication, and S3-backed image storage.
- `infrastructure/`: Deployment, environment, and AWS EC2/S3/PostgreSQL operational assets.
- `docs/`: Architecture, API, database, deployment, and roadmap documentation.

### Request Flow

1. A user registers or logs in from the frontend.
2. The backend issues a JWT access token.
3. The user creates a new foot scan.
4. The frontend requests an image upload URL or uploads an image through the backend upload API.
5. The backend stores image metadata in PostgreSQL and delegates object storage to the S3 abstraction.
6. The scan is queued or marked ready for AI processing.
7. The placeholder AI pipeline accepts the scan, records status transitions, and returns a stub measurement/recommendation result.
8. The dashboard and scan history consume scan status and result APIs.

### Future AI Pipeline

```text
Image Upload
  -> Image Validation Service
  -> Foot Segmentation Service
  -> Measurement Service
  -> Size Recommendation Service
  -> Results API
```

Each AI stage is represented by an interface so SAM, YOLOv8 Segmentation, Depth Anything V2, and Hugging Face Transformers can be introduced later without rewriting API controllers or persistence models.

Phase 3A adds `ImageValidationService` as a pre-AI quality gate. Phase 3B adds `SAM2FootSegmentationService`, which uses Hugging Face SAM 2 mask generation to power foot count, bounding boxes, segmentation confidence, and edge-contact detection. Depth Anything V2 should later provide depth-aware camera-angle validation before measurement.

## 2. Folder Structure

```text
.
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/
│   │   │   ├── dashboard/
│   │   │   ├── profile/
│   │   │   └── scans/
│   │   │       ├── new/
│   │   │       └── [scanId]/
│   │   ├── camera/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   ├── lib/
│   ├── public/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── scans.py
│   │   │       ├── uploads.py
│   │   │       └── ai.py
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── ai/
│   │   │   └── storage/
│   │   └── main.py
│   ├── alembic/
│   ├── pyproject.toml
│   └── README.md
├── infrastructure/
│   ├── docker/
│   ├── aws/
│   └── README.md
└── docs/
```

## 3. Database Schema

### `users`

Stores authenticated users. This platform is women-only by product policy, but gender is still represented as profile metadata for future compliance and analytics decisions.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Internal identifier |
| `email` | VARCHAR(320), unique | Login identity |
| `password_hash` | TEXT | Argon2 or bcrypt hash |
| `first_name` | VARCHAR(100) | Optional |
| `last_name` | VARCHAR(100) | Optional |
| `gender` | VARCHAR(32) | Default `woman` |
| `date_of_birth` | DATE | Optional |
| `country_code` | VARCHAR(2) | Optional ISO-3166 |
| `is_active` | BOOLEAN | Soft access control |
| `is_verified` | BOOLEAN | Email verification readiness |
| `created_at` | TIMESTAMPTZ | Server-generated |
| `updated_at` | TIMESTAMPTZ | Server-generated |

### `foot_scans`

Represents a measurement workflow for one foot.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Scan identifier |
| `user_id` | UUID FK users.id | Owner |
| `foot_side` | VARCHAR(16) | `left`, `right`, or `unknown` |
| `status` | VARCHAR(32) | `created`, `image_uploaded`, `processing`, `completed`, `failed` |
| `length_mm` | NUMERIC(6,2) | Future AI output |
| `width_mm` | NUMERIC(6,2) | Future AI output |
| `arch_height_mm` | NUMERIC(6,2) | Future depth output |
| `confidence_score` | NUMERIC(5,4) | Future model confidence |
| `validation_status` | VARCHAR(32) | `passed`, `failed`, or null |
| `validation_issues` | JSONB | Human-readable validation issues |
| `processing_error` | TEXT | Failure detail |
| `created_at` | TIMESTAMPTZ | Server-generated |
| `updated_at` | TIMESTAMPTZ | Server-generated |

### `uploaded_images`

Stores S3 metadata and relationship to a foot scan.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Image identifier |
| `user_id` | UUID FK users.id | Owner |
| `foot_scan_id` | UUID FK foot_scans.id | Nullable until attached |
| `bucket` | VARCHAR(255) | S3 bucket |
| `object_key` | TEXT | S3 object key |
| `content_type` | VARCHAR(100) | MIME type |
| `byte_size` | BIGINT | File size |
| `checksum_sha256` | VARCHAR(64) | Optional integrity check |
| `upload_status` | VARCHAR(32) | `pending`, `uploaded`, `failed` |
| `created_at` | TIMESTAMPTZ | Server-generated |

### `shoe_recommendations`

Stores generated sizing recommendations.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Recommendation identifier |
| `foot_scan_id` | UUID FK foot_scans.id | Source scan |
| `region` | VARCHAR(16) | `US`, `UK`, `EU`, etc. |
| `size_value` | VARCHAR(20) | Size label |
| `width_category` | VARCHAR(32) | `narrow`, `standard`, `wide`, etc. |
| `brand` | VARCHAR(120) | Optional future brand-specific result |
| `confidence_score` | NUMERIC(5,4) | Recommendation confidence |
| `rationale` | TEXT | Human-readable explanation |
| `created_at` | TIMESTAMPTZ | Server-generated |

### `audit_logs`

Append-only security and operational audit trail.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Log identifier |
| `user_id` | UUID FK users.id | Nullable for anonymous events |
| `action` | VARCHAR(120) | Event name |
| `entity_type` | VARCHAR(80) | Affected resource |
| `entity_id` | UUID | Nullable resource ID |
| `ip_address` | INET | Request origin |
| `user_agent` | TEXT | Request agent |
| `metadata` | JSONB | Redacted structured context |
| `created_at` | TIMESTAMPTZ | Server-generated |

## 4. API Endpoints

All backend routes are versioned under `/api/v1`.

### Authentication API

- `POST /auth/register`: Create account.
- `POST /auth/login`: Authenticate and return JWT access token.
- `POST /auth/refresh`: Refresh token placeholder.
- `POST /auth/logout`: Client logout/audit endpoint.
- `GET /auth/me`: Return current authenticated user.

### User Management API

- `GET /users/me`: Current user profile.
- `PATCH /users/me`: Update profile.
- `DELETE /users/me`: Deactivate account.

### Foot Scan API

- `POST /scans`: Create a scan.
- `GET /scans`: List current user's scans.
- `GET /scans/{scan_id}`: Read scan details.
- `PATCH /scans/{scan_id}`: Update scan metadata.
- `DELETE /scans/{scan_id}`: Soft-delete or archive scan placeholder.

### Image Upload API

- `POST /uploads/presign`: Create a presigned S3 upload contract.
- `POST /uploads/complete`: Mark upload completed and attach metadata.
- `GET /uploads/{image_id}`: Retrieve image metadata.

### Scan History API

- `GET /scans/history`: Paginated scan history with recommendation summaries.

### AI Processing Placeholder API

- `POST /ai/scans/{scan_id}/process`: Start placeholder processing.
- `GET /ai/scans/{scan_id}/status`: Return processing status.
- `GET /ai/scans/{scan_id}/results`: Return measurements and recommendations when available.

## 5. Backend Service Design

### API Layer

FastAPI routers own HTTP concerns only: request validation, dependency injection, response models, and status codes.

### Service Layer

- `AuthService`: Password hashing, credential verification, JWT issuing.
- `UserService`: Profile lifecycle and account state.
- `FootScanService`: Scan creation, status transitions, scan history.
- `UploadService`: Upload contract creation, S3 metadata persistence.
- `StorageService`: S3 abstraction for presigned uploads and object metadata.
- `AIProcessingService`: Orchestrates placeholder AI stages.

### AI Service Contracts

- `FootSegmentationService`: Future SAM or YOLOv8 segmentation adapter.
- `MeasurementService`: Future pixel-to-millimeter and depth-aware measurement adapter.
- `SizeRecommendationService`: Sizing rules and future brand-specific model adapter.
- `AIModelProvider`: Future Hugging Face model loading/inference boundary.

## 6. Frontend Page Hierarchy

- `/`: Landing page.
- `/login`: Login page.
- `/register`: Register page.
- `/dashboard`: Authenticated dashboard summary.
- `/scans`: Scan history.
- `/scans/new`: New foot scan setup.
- `/camera`: Camera capture experience.
- `/scans/[scanId]`: Scan detail and result state.
- `/profile`: User profile.

## 7. Environment Variables

### Backend

- `APP_ENV`: `local`, `staging`, or `production`.
- `API_HOST`: FastAPI bind host.
- `API_PORT`: FastAPI bind port.
- `DATABASE_URL`: PostgreSQL connection string.
- `JWT_SECRET_KEY`: High-entropy signing secret.
- `JWT_ALGORITHM`: Default `HS256`.
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime.
- `AWS_REGION`: S3 region.
- `AWS_S3_BUCKET`: S3 bucket for uploads.
- `AWS_ACCESS_KEY_ID`: Runtime credential when not using an instance role.
- `AWS_SECRET_ACCESS_KEY`: Runtime credential when not using an instance role.
- `S3_PRESIGN_EXPIRE_SECONDS`: Presigned URL lifetime.
- `CORS_ALLOWED_ORIGINS`: Comma-separated frontend origins.
- `LOG_LEVEL`: Runtime log level.

### Frontend

- `NEXT_PUBLIC_API_BASE_URL`: Backend API base URL.
- `NEXT_PUBLIC_APP_NAME`: Display name.
- `NEXT_PUBLIC_ENVIRONMENT`: Frontend environment label.

## 8. Development Roadmap

### Phase 1: Foundation

- Monorepo structure.
- FastAPI service skeleton.
- Next.js page hierarchy.
- PostgreSQL schema and migrations.
- JWT auth.
- S3 upload abstraction.
- AI service contracts and placeholder processing.

### Phase 2: Product Workflow

- Camera capture UX.
- Upload completion flow.
- Scan status polling.
- User-facing scan history and result state.
- Email verification and password reset.

### Phase 3: Measurement Intelligence

- Segmentation adapter for SAM and YOLOv8.
- Depth Anything V2 adapter for depth estimation.
- Calibration strategy for real-world scale.
- Rule-based initial women's shoe size recommendation.

### Phase 4: Model Operations

- Batch inference workers.
- Model registry and versioning.
- Human QA review tools.
- Monitoring of model drift, confidence, and failure modes.

### Phase 5: Production Hardening

- CI/CD.
- Observability.
- Rate limiting and abuse protection.
- Data retention workflows.
- Privacy and compliance reviews.

## 9. Security Considerations

- Store passwords using a memory-hard hash such as Argon2id, with bcrypt as an acceptable fallback.
- Use JWT access tokens with short expiration and future refresh-token rotation.
- Never expose AWS secret keys to the frontend.
- Prefer EC2 instance profiles or ECS task roles over static AWS keys in production.
- Restrict S3 object keys by user and scan namespace.
- Validate upload content type and size before issuing upload contracts.
- Keep uploaded foot images private; serve via short-lived signed URLs only when needed.
- Apply CORS allowlists per environment.
- Add request rate limiting for auth, upload, and AI processing routes.
- Keep audit logs append-only and avoid storing raw secrets or full JWTs in metadata.
- Encrypt PostgreSQL storage and S3 buckets at rest.
- Use TLS termination through ALB, Nginx, or Caddy on EC2.
- Treat foot images and measurements as sensitive biometric-adjacent data.

## 10. Production Deployment Strategy

### AWS EC2 Baseline

- Provision EC2 instance in a private subnet where practical.
- Use an ALB or reverse proxy for TLS, HTTP to HTTPS redirects, and health checks.
- Run backend with Uvicorn/Gunicorn behind the proxy.
- Run Next.js as a standalone Node process or deploy separately to a frontend host.
- Use PostgreSQL via Amazon RDS for production.
- Use S3 for private image storage.
- Use IAM roles for AWS access.

### Deployment Flow

1. Build frontend assets.
2. Build backend package or container image.
3. Run database migrations.
4. Restart application services with health checks.
5. Verify `/health`, frontend root, auth routes, and upload presign route.
6. Roll back by redeploying previous image and preserving database backups.

### Observability

- Structured JSON logs.
- Request ID propagation.
- Application health endpoint.
- Metrics for auth failures, scan creation, upload completion, AI processing status, and recommendation generation.
- Alerts for elevated 5xx rates, database connection saturation, S3 failures, and queue backlog when async processing is introduced.

# API Endpoints

Base path: `/api/v1`

## Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

## Users

- `GET /users/me`
- `PATCH /users/me`
- `DELETE /users/me`

## Scans

- `POST /scans`
- `GET /scans?limit=25&offset=0`
- `GET /scans/history`
- `GET /scans/{scan_id}`
- `GET /scans/{scan_id}/capture-sessions`
- `PATCH /scans/{scan_id}`
- `DELETE /scans/{scan_id}`

## Uploads

- `POST /uploads/presign`
- `POST /uploads/complete`
- `GET /uploads/{image_id}`

## AI Placeholder

- `POST /ai/scans/{scan_id}/process`
- `POST /ai/scans/{scan_id}/validate`
- `POST /ai/capture-quality`
- `POST /ai/scans/{scan_id}/capture-quality`
- `POST /ai/scans/{scan_id}/measure`
- `POST /ai/scans/{scan_id}/detect-reference-object`
- `POST /ai/scans/{scan_id}/scale-estimate`
- `POST /ai/scans/{scan_id}/shoe-size`
- `POST /ai/scans/{scan_id}/run-full-pipeline`
- `GET /ai/scans/{scan_id}/status`
- `GET /ai/scans/{scan_id}/results`

Validation responses include `valid`, `issues`, `foot_count`, `segmentation_confidence`, and `foot_bbox`.

Capture-quality requests preserve the original flat response by default. When `persist_session=true`, the response is wrapped as `{ "capture_quality": {...}, "capture_session_id": "..." }`.

Reference-object detection accepts a selected mode plus optional manual bbox/polygon. It returns `detected=false` with instructions when the object is missing, cropped, distorted, overlapping the foot, or below confidence gates.

Scale-estimate requests return `available`, `low_confidence`, `unavailable`, or `needs_reference`. Requests can include `reference_object_detection` to run detection before scale estimation. Millimeter fields stay null unless the pixel measurement is trusted and scale confidence is sufficient.

Shoe-size requests return either a women-only generic recommendation or a structured blocked response. Recommendations are blocked unless measurement and scale are trusted.

Full-pipeline requests return stage statuses for capture quality, measurement, landmark validation, scale, and optional shoe size recommendation. They can also include `reference_object_detection` so reference validation happens before scale.

## Capture Sessions

- `POST /capture-sessions`
- `GET /capture-sessions?limit=25&offset=0`
- `GET /capture-sessions/{capture_session_id}`
- `PATCH /capture-sessions/{capture_session_id}/attach`

Capture sessions store device metadata, camera/video telemetry, capture-quality scores, issues, guidance instructions, and optional links to a scan and uploaded image. Users can only access their own sessions.

## Phase 2 Workflow

1. `POST /auth/register`
2. `POST /auth/login`
3. `POST /scans`
4. `POST /uploads/presign` with `foot_scan_id`
5. `PUT` image bytes to the returned S3 presigned URL
6. `POST /uploads/complete` with `image_id` and `foot_scan_id`
7. `GET /scans/{scan_id}`
8. `GET /scans/history?limit=10&offset=0`
## Validation Cases

- `POST /api/v1/validation-cases` creates a real-device validation case.
- `GET /api/v1/validation-cases` lists the current user's validation cases.
- `GET /api/v1/validation-cases/summary` returns case counts by status/device/scenario.
- `GET /api/v1/validation-cases/{id}` reads one case.
- `PATCH /api/v1/validation-cases/{id}` updates case metadata, ground truth, or annotation fields.
- `DELETE /api/v1/validation-cases/{id}` deletes one case.
- `POST /api/v1/validation-cases/{id}/attach-upload` links an uploaded image.
- `POST /api/v1/validation-cases/{id}/link-scan` links a scan and optional capture session.
- `POST /api/v1/validation-cases/{id}/mark-benchmark-ready` enforces image, ground truth, scan, and reference evidence gates.
- `POST /api/v1/validation-cases/{id}/run-benchmark` records benchmark errors or exact blocker reasons.

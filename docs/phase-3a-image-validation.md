# Phase 3A Image Validation Layer

## Goal

Phase 3A adds an image quality gate before future AI processing. It does not implement measurement, shoe size recommendations, SAM 2 inference, YOLOv8 inference, or Depth Anything V2 inference.

## Validation Response

```json
{
  "valid": false,
  "issues": [
    "Foot is partially outside frame",
    "Lighting is too dark"
  ]
}
```

## Backend Design

`ImageValidationService` lives at `backend/app/services/image_validation_service.py`.

Responsibilities:

- Validate that exactly one clear foot candidate is visible.
- Detect blurry images.
- Detect low-light images.
- Detect overexposed images.
- Detect incorrect camera angle.
- Detect partial foot visibility.
- Return human-readable validation issues.

## Validation Layers

- `ImageValidationService`: Orchestrates image decoding, quality checks, and foot-frame checks.
- `HeuristicFootFrameAnalyzer`: Current lightweight analyzer for foot count, frame edge contact, and likely camera-angle problems.
- `FootFrameAnalyzer`: Protocol used to replace heuristics with future model adapters.

## Future Model Adapter Path

SAM 2 should be introduced as a `FootFrameAnalyzer` implementation that returns foot masks, mask count, bounding boxes, edge contact, and segmentation confidence.

Depth Anything V2 should be introduced behind a depth/pose adapter that returns relative depth maps, foot-plane consistency, camera obliqueness, and perspective distortion signals.

## API Integration

`POST /api/v1/ai/scans/{scan_id}/validate`

Returns:

```json
{
  "valid": true,
  "issues": []
}
```

`POST /api/v1/ai/scans/{scan_id}/process`

This endpoint now validates the latest uploaded image before any AI processing. If validation fails:

- `foot_scans.status` becomes `validation_failed`.
- `foot_scans.validation_status` becomes `failed`.
- `foot_scans.validation_issues` stores the structured list of issues.
- `foot_scans.processing_error` stores a human-readable joined summary.

If validation passes:

- `foot_scans.status` becomes `validation_passed`.
- `foot_scans.validation_status` becomes `passed`.
- Measurement and recommendation logic remains unimplemented.

## Database Migration

Migration added:

`backend/alembic/versions/0002_scan_validation_fields.py`

New columns:

```sql
ALTER TABLE foot_scans ADD COLUMN validation_status VARCHAR(32);
ALTER TABLE foot_scans ADD COLUMN validation_issues JSONB;
```

## Frontend Integration

The scan detail page now includes an image validation action. It displays validation status, issue count, and the human-readable issue list.

## Current Limitations

Phase 3B replaces the foot-count and partial-frame heuristics with SAM 2 segmentation. Camera-angle validation remains lightweight until Depth Anything V2 is integrated.

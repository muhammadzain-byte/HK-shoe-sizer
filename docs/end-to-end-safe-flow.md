# End-To-End Safe Flow

## What Was Built

Phase 4F adds `ScanOrchestrationService` and `POST /api/v1/ai/scans/{scan_id}/run-full-pipeline`.

The flow connects guided capture, capture quality, measurement, landmark trust, scale estimation, and optional women-only shoe size recommendation.

## Gate Order

1. Confirm the user owns the scan.
2. Confirm an uploaded image exists.
3. Confirm capture quality is ready.
4. Confirm or run pixel measurement.
5. Require trusted measurement/landmarks.
6. Estimate scale from reference object or supported depth metadata.
7. If scale is available and requested, run women-only size recommendation.

Phase 5A allows the full-pipeline request to include `reference_object_detection`. When enabled, the backend validates or detects the selected reference object before scale estimation.

## Overall Statuses

- `capture_needs_adjustment`
- `measurement_needs_review`
- `scale_unavailable`
- `ready_for_size`
- `size_recommended`
- `failed`

## Safe Blocking

If capture quality is rejected or not ready, measurement and sizing are not run.

If measurement is not trusted, scale and sizing are blocked.

If scale is unavailable or low confidence, shoe size is blocked.

If reference-object detection fails, scale returns `needs_reference` and shoe size remains blocked.

If shoe size is requested without trusted millimeter length and width, the engine returns a structured blocked response.

## Example Blocked Response

```json
{
  "overall_status": "scale_unavailable",
  "next_action": "Use a reference object or supported depth mode for real-world scale.",
  "user_message": "Scale is unavailable, so shoe size is blocked."
}
```

## Example Successful Path

With ready capture, trusted measurement, valid reference-object scale, and `run_shoe_size=true`, the flow can return:

```json
{
  "overall_status": "size_recommended",
  "user_message": "Recommended women's EU size: 39."
}
```

This remains an advisory generic chart result, not a brand-specific production guarantee.

## MirrorSize-Style Scope

The flow resembles a guided measurement product: guide capture, validate quality, measure, validate trust, determine scale, then optionally size. It does not copy proprietary code and does not fake unsupported depth or scale.

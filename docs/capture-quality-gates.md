# Capture Quality Gates

## What Was Built

`CaptureQualityService` analyzes image frame quality, foot visibility, pose quality, and distance quality. It returns:

- `ready`
- `needs_adjustment`
- `reject`

The result includes scores, issues, instructions, and a primary guidance message.

Phase 4B can persist the result to `capture_sessions` when callers pass `persist_session=true`.

## Checks

- Blur via Laplacian variance.
- Lighting and overexposure via luminance histogram.
- Foot detection and one-foot-only status via segmentation.
- Toe, heel, and side margins from the selected foot bounding box.
- Lower-leg ratio from refinement metadata when available.
- Too-close and too-far checks from bbox coverage and height.
- Pose/tilt risk from bbox aspect and optional device orientation.

## Safe Behavior

Rejects unreadable images, very blurry images, low light, overexposure, no foot, or multiple feet. Gives adjustment instructions for cropped toes, missing heel, too much lower leg, foot off-center, wrong angle, too close, or too far.

## Unsafe Behavior

Capture quality does not equal measurement quality. Passing capture quality only means the image can proceed to segmentation and measurement validation.

Persisted capture quality does not equal real-world scale. Pixel measurements must still be blocked from centimeter/millimeter output until a trusted scale source exists.

## Requires Real Device Testing

Thresholds should be tested with real captured images across camera models, lighting conditions, foot sizes, skin tones, and floor/background types.

## Future Dataset/Training

Collected Phase 4B telemetry can support better thresholds and a future capture-quality model.

Telemetry should be used with privacy safeguards. Do not log raw image bytes or expose device metadata outside authenticated user flows.

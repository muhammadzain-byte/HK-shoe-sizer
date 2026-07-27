# Capture Session Telemetry

## What Was Built

Phase 4B adds persistent `capture_sessions` records for guided capture attempts and capture-quality validations. A capture session stores the authenticated user, optional scan, optional uploaded image, capture-quality status, quality scores, guidance instructions, device metadata, and raw JSON snapshots for debugging.

## Why It Matters

Capture telemetry is the data foundation for future scale estimation and calibration. It lets the system compare capture quality against device family, camera facing mode, video resolution, viewport size, orientation, and later measurement outcomes.

## Stored Data

- Capture status, quality score, issues, and instructions.
- Frame quality: blur, lighting, and overexposure.
- Foot visibility: toe, heel, full-foot visibility, margins, and lower-leg ratio.
- Pose and distance quality signals.
- User agent-derived browser, OS, device type, and device family.
- Video, viewport, device pixel ratio, camera facing mode, orientation, and motion metadata.
- Raw device metadata and raw capture-quality result for reproducible debugging.

## What Is Intentionally Not Built

Telemetry does not provide real-world scale. It does not convert pixels to millimeters, run AR/depth, recommend shoe size, or train a model. If scale is unavailable later, the measurement pipeline must still return a safe blocked state.

## Safe Behavior

Only authenticated users can access their own capture sessions. Scan and upload attachments are checked against the current user before they are stored.

## Unsafe Behavior

It is unsafe to expose capture telemetry publicly or treat device metadata as proof of real-world measurement accuracy. Uploaded foot images and related telemetry are sensitive biometric-like data and must be protected.

## Privacy Notes

Do not store raw image bytes in logs. Do not log secrets or presigned URLs. Avoid storing unnecessary personal data beyond capture debugging needs. Future admin analytics should be permissioned separately.

## Retention Recommendation

Retain uploaded foot images and telemetry only as long as needed for user-facing history, debugging, and explicit product improvement consent. Add deletion/export tools before using this data for dataset collection or model training.

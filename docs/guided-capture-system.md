# Guided Capture System

## What Was Built

The camera page now uses rear-camera preference, high-resolution video constraints, a live foot guide overlay, local readiness state, orientation-aware guidance, and a backend capture-quality check after capture.

The guide has toe, midfoot, heel, and side margin zones. Phase 5A adds an optional reference-object mode with a separate reference zone for credit card, A4 paper, calibration card, or custom object captures. The capture button is disabled until the local state is ready, with an explicit capture-for-review path when local guidance is not ready.

## What Is Not Built Yet

This is not real-time SAM 2 streaming. The browser does lightweight guidance locally and the backend validates captured still images.

Phase 4B now stores capture-session telemetry when requested. That storage records the device metadata and capture-quality result, but it still does not provide real-world scale.

## Safe Behavior

The UI can block clearly unready captures, warn about tilt, and reject backend-flagged captures. Backend results return user-facing instructions such as moving closer, moving higher, centering the foot, showing toes, showing heel, improving light, or reducing lower-leg visibility.

## Unsafe Behavior

The live browser guide should not be treated as final measurement validation. It does not provide scale or shoe size.

Capture telemetry should not be exposed publicly or used as a substitute for measurement-grade validation.

Reference-object mode only improves scale readiness. Millimeter conversion still requires backend validation and confidence gates.

## Requires Real Device Testing

Camera constraints, rear-camera selection, video dimensions, orientation permission behavior, and lighting/blur behavior need testing on common phones.

## Future Dataset/Training

A future dataset could improve live pose estimation, but Phase 4A intentionally uses explainable heuristics and backend segmentation.

# AR / Depth Strategy

## What Was Built

Phase 4D makes the backend adapter-ready for future AR/depth capture. It adds depth contracts, validation, placeholder providers, and a depth scale adapter.

No native ARCore, ARKit, LiDAR runtime, browser depth runtime, or monocular model runtime is implemented.

## Backend Depth Metadata

The backend can accept depth metadata with:

- Depth mode: `arcore`, `arkit`, `lidar`, `uploaded_depth`, `monocular`, or `none`.
- Camera intrinsics: `fx`, `fy`, `cx`, `cy`, `width`, and `height`.
- Floor or foot plane distance.
- Depth confidence.
- Plane confidence.
- Source device and raw metadata.

## Validation Gates

Depth scale is blocked unless:

- Depth is available.
- Mode is supported.
- Intrinsics are complete.
- Plane confidence is at least `0.80`.
- Depth confidence is at least `0.80`.
- Distance to the foot plane is available.
- Capture quality is ready.
- Measurement status is trusted.

Weak depth returns `low_confidence` or `unavailable`.

## Depth Scale Adapter

The adapter can use a conservative pinhole approximation only when all gates pass. It uses distance to the foot plane and camera focal length in pixels to estimate `mm_per_pixel`.

This is adapter readiness, not production AR measurement accuracy.

## Web Limitations

Standard mobile browsers usually do not expose reliable raw depth, camera intrinsics, or floor-plane estimates. Web-only capture should prefer a reference object or calibration mat for scale.

## Native Options

Native Android can later use ARCore. Native iOS can later use ARKit and LiDAR where available. Both require real device testing and calibration validation before production sizing.

## Monocular Depth

Monocular depth remains blocked for millimeter conversion unless calibrated and validated. It may help future guidance, but it is not enough by itself for sizing.

# Scale Estimation Service

## What Was Built

Phase 4C adds `ScaleEstimationService`, `scale_estimates`, and `POST /api/v1/ai/scans/{scan_id}/scale-estimate`.

Phase 4D adds depth validation and a depth scale adapter for future AR/depth clients.

Phase 5A adds `ReferenceObjectDetectionService` and lets scale-estimate requests run reference-object detection before estimating scale.

The service decides whether pixel measurements can safely be converted into millimeters. By default, scale is unavailable.

## Why Pixels Are Not Real Measurements

A pixel count depends on camera distance, focal length, sensor crop, perspective, resolution, and image scaling. Two images of the same foot can have different pixel lengths. Pixels cannot become millimeters without a trusted scale source.

## Supported Modes

- `reference_object`: implemented when a known object bbox and known dimensions are provided.
- `calibration_mat`: safe placeholder with simple marker spacing support.
- `ar_depth`: adapter-ready via uploaded metadata; no native ARCore or ARKit runtime is implemented.
- `device_camera_model`: architecture only; device metadata alone is not enough.
- `monocular_depth_model`: safe placeholder; uncalibrated monocular depth does not output millimeters.
- `unavailable`: default safe mode.

## Safe Reference Object Mode

A reference object can produce scale only when:

- Known width and height are available.
- Pixel bbox width and height are available.
- Detection confidence is at least `0.85`.
- Width-derived and height-derived scale are consistent.
- Same-plane evidence is acceptable when provided.
- Distortion is below the safe threshold.

If detection fails, the response uses `scale_status = "needs_reference"` and returns retake instructions.

Example available response:

```json
{
  "scale_status": "available",
  "scale_mode": "reference_object",
  "pixels_per_mm": 10.0,
  "mm_per_pixel": 0.1,
  "confidence": 0.93,
  "evidence": {
    "reference_object_type": "credit_card",
    "reference_width_pixels": 856,
    "reference_height_pixels": 540,
    "known_width_mm": 85.6,
    "known_height_mm": 53.98
  },
  "issues": [],
  "instructions": []
}
```

## Default Unavailable Response

```json
{
  "scale_status": "unavailable",
  "scale_mode": "unavailable",
  "pixels_per_mm": null,
  "mm_per_pixel": null,
  "confidence": 0.0,
  "evidence": {},
  "issues": ["No trusted scale source was provided."],
  "instructions": ["Use a reference object or supported depth capture mode for real-world sizing."]
}
```

## Real-World Measurement Gate

`foot_length_mm` and `foot_width_mm` stay `null` unless:

- `measurement_status` is `trusted`.
- `scale_status` is `available`.
- scale confidence is at least `0.85`.
- `mm_per_pixel` is available.

Shoe size recommendation remains blocked unless the real-world measurement gate passes.

## What Is Not Built

This phase does not implement ARCore, ARKit, real native depth runtime, fake monocular scale, training, fine-tuning, or production accuracy claims.

## Depth Adapter

Depth metadata can produce scale only when measurement is trusted, capture quality is ready, intrinsics are complete, depth and plane confidence are strong, and distance to the foot plane exists. Otherwise it returns `low_confidence` or `unavailable`.

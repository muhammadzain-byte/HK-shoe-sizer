# Scale Estimation Strategy

## What Was Built

Phase 4C adds safe scale estimation architecture. The system can represent reference objects, calibration mats, AR/depth metadata, device camera profiles, monocular depth placeholders, and unavailable scale.

Reference-object scale can be calculated when valid dimensions, bbox, confidence, and consistency are provided. All other modes default to safe blocked behavior unless trusted evidence exists.

Phase 4D adds depth validation and a depth scale adapter. Strong synthetic AR/depth metadata can produce scale in tests, but native AR runtime is still not implemented.

Phase 5A adds reference-object capture UX and conservative reference-object detection/validation. This improves test readiness, not production accuracy by itself.

## Why Scale Is Required

Pixel foot length and width are not real-world measurements. Camera distance, perspective, focal length, sensor size, resolution, and resizing all change the pixel count. Millimeters require a trusted pixels-per-mm or mm-per-pixel scale.

## Supported Modes

1. `reference_object`: implemented with confidence and distortion checks.
2. `calibration_mat`: safe placeholder with simple marker spacing support.
3. `ar_depth`: adapter-ready for future AR/depth clients, with strict metadata gates.
4. `device_camera_model`: architecture only; metadata alone cannot produce scale.
5. `monocular_depth_model`: placeholder only; no fake no-reference scale.
6. `unavailable`: default.

## Safe Behavior

If scale is unavailable, length and width in millimeters stay `null`. If measurement is not trusted, scale is blocked. If confidence is below threshold, real-world conversion is blocked.

## Reference Object Is Safest For Web

Web browsers cannot reliably expose calibrated camera intrinsics or depth on all devices. A clearly visible known object in the same plane as the foot is the safest near-term web path. The object must be fully visible, flat, high confidence, low distortion, and not overlapping the foot.

## Accuracy Validation

The validation harness compares AI millimeter results against manual ground truth. Until real-device cases are collected and reviewed, the system must not claim production measurement accuracy.

## AR And Depth

ARCore and ARKit need real device integration and validation. Uploaded depth metadata can be represented now, but it does not produce millimeters until confidence and calibration are proven.

## Monocular Depth

Monocular depth can support guidance and future research, but it is not enough by itself for shoe sizing. Without calibration or ground-truth validation, it returns unavailable.

## Shoe Size Remains Blocked

Phase 4E adds a women-only generic size engine. Shoe sizing remains blocked until measurement quality is trusted and scale is available with sufficient confidence.

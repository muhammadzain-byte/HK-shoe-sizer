# Cross-platform AR capture contract

The hosted web app provides guided browser capture on Android, iPhone, and desktop. Browser capture is intentionally **not** a no-reference metric-scale source because ordinary browsers do not reliably expose calibrated intrinsics, a stable floor plane, and camera-to-foot distance.

## Native capture evidence

An Android ARCore client, an iOS ARKit/LiDAR client, or a verified native wrapper may submit capture metadata with `capture_mode` set to `arcore`, `arkit`, or `lidar`, plus `ar_evidence` containing:

- `depth_available: true`
- matching `depth_mode`
- `fx`, `fy`, `cx`, `cy`, image width, and image height
- `distance_to_foot_plane_mm`
- `depth_confidence` and `plane_confidence`
- capture timestamp and provider/device metadata in `raw`

The backend accepts this only after capture quality and anatomical measurement status are trusted. It rejects absent/incomplete intrinsics, confidence below 0.80, image/intrinsics mismatch, and implausible 250–2500 mm capture distance. A native source must still be benchmarked against real ground truth before any production accuracy claim.

## Safe fallbacks

- Browser guidance: pixel measurements only, or reference object/calibration mat.
- Weak AR evidence: `low_confidence`; no millimetres and no size recommendation.
- Untrusted capture or landmarks: blocked before scale conversion.

This is an original implementation. It does not reproduce proprietary MS ShoeSizer code, models, or UI.

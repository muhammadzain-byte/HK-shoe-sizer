# Phase 3C Foot Measurement Engine

## Scope

Phase 3C converts a selected single-foot mask into pixel-only geometry.

This phase does not implement:

- Depth Anything V2.
- Real-world calibration.
- Centimeter measurements.
- Shoe size recommendations.
- Dataset collection.
- Model training.

## Architecture

```text
User Image
  -> SAM 2
  -> Foot Candidate Selection
  -> Single Foot Mask
  -> MeasurementService
  -> foot_measurements row
  -> Pixel measurement response
```

## Database

Migration:

`backend/alembic/versions/0003_foot_measurements.py`

New table:

`foot_measurements`

Stores pixel length, pixel width, heel/toe points, width endpoints, model metadata, confidence, status, and creation time.

## Updated Architecture

Phase 3C.1 refines the measurement engine from pure PCA extremities to anatomical landmark detection:

```text
Selected Foot Mask
  -> Binary mask normalization
  -> Largest contour extraction
  -> PCA orientation frame
  -> Canonical foot coordinate system
  -> Heel region analysis
  -> Toe region analysis
  -> Forefoot region analysis
  -> MeasurementQualityAnalyzer
  -> Anatomical measurement overlay
  -> Comparison overlay
```

PCA is now used only to establish the foot axis and canonical coordinate system. Landmark detection is performed within anatomical regions.

## Mathematical Approach

`MeasurementService` uses OpenCV and PCA:

1. Normalize the selected mask to a binary image.
2. Extract external contours using `cv2.findContours`.
3. Select the largest contour.
4. Compute PCA over contour points.
5. Use the first principal component as the long axis of the foot.
6. Use the second principal component as the width axis.
7. Rotate/project points into canonical coordinates.
8. Detect anatomical landmarks from heel, toe, and forefoot regions.

## PCA Explanation

PCA finds the dominant direction of variance in the contour points. For a foot-shaped mask, the largest variance should align with the heel-to-toe axis. The perpendicular component approximates the width axis.

This gives a rotation-invariant way to measure pixel length and width without assuming the foot is perfectly vertical in the image.

## Anatomical Measurement Algorithm

### 1. Foot Orientation

The engine computes PCA over the largest contour and projects all mask pixels into a canonical frame:

- `v`: heel-to-toe axis.
- `u`: width axis perpendicular to the foot.

The orientation is normalized so heel and toe regions can be reasoned about consistently.

### 2. Heel Detection Strategy

The engine identifies the bottom heel band of the canonical foot mask, then computes the center of the heel region rather than using a contour extremity. This produces `heel_center`.

### 3. Toe Detection Strategy

The engine analyzes the upper toe band, clusters toe-like protrusions, marks all candidate toe tips, and selects the candidate farthest from the heel center as `longest_toe_point`.

### 4. Forefoot Width Detection Strategy

The engine ignores heel and toe bands, scans the forefoot/ball-of-foot region, and finds the maximum span along the width axis. The resulting line is perpendicular to the foot axis and constrained to the forefoot region.

### 5. Quality Validation

`MeasurementQualityAnalyzer` detects:

- heel ambiguity
- toe ambiguity
- low-confidence contours
- unusual foot shape
- overlapping feet

It returns a pixel-measurement confidence score.

## API

`POST /api/v1/ai/scans/{scan_id}/measure`

Returns pixel-only measurements:

```json
{
  "measurement_status": "completed",
  "foot_length_pixels": 1320.54,
  "foot_width_pixels": 498.12,
  "heel_point": {
    "x": 220,
    "y": 1198
  },
  "toe_point": {
    "x": 242,
    "y": 81
  },
  "width_points": {
    "left": {
      "x": 101,
      "y": 610
    },
    "right": {
      "x": 602,
      "y": 610
    }
  },
  "confidence_score": 0.91
}
```

## Verification Script

`backend/scripts/test_measurement_engine.py`

Example:

```bash
python backend/scripts/test_measurement_engine.py --image paon.png
```

Generated files:

- `measurement_overlay.png`
- `anatomical_measurement_overlay.png`
- `measurement_comparison_overlay.png`
- `measurement_metadata.json`

## Known Limitations

- Pixel measurements are not real-world measurements.
- No camera calibration is applied.
- No depth information is used.
- Accuracy depends on SAM 2 candidate quality.
- Overlapping feet or partial feet can distort PCA and width detection.
- Heel/toe orientation is inferred geometrically and may fail on unusual poses.

## Future Calibration Strategy

Future phases should add:

- Depth Anything V2 for pose/depth validation.
- Reference-object or camera-based scale calibration.
- Pixel-to-millimeter conversion.
- Confidence models trained on real scan QA.
- Shoe size recommendation only after calibrated real-world dimensions exist.

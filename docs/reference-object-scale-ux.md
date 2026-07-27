# Reference Object Scale UX

Phase 5A adds a practical web-first path for real-world scale: a known reference object placed flat beside the foot.

## Built

- Camera capture lets the user choose no reference object, credit card, A4 paper, calibration card, or custom object.
- The camera guide shows a separate reference-object zone when a mode is selected.
- Scan detail exposes reference-object detection, scale estimation, and full analysis using the selected mode.
- Backend validation accepts manual bbox/polygon input and can attempt conservative rectangular detection from the scan image.

## Safe Instructions

- Place the object flat on the same floor plane as the foot.
- Keep the object fully visible.
- Do not hold it in your hand.
- Do not place it under the foot.
- Avoid tilt, crop, overlap, or perspective distortion.

## Supported Now

- Credit card default size: 85.60 mm by 53.98 mm.
- A4 paper default size: 210 mm by 297 mm.
- Calibration card and custom object require dimensions.

## Not Built Yet

- Production-grade automatic credit-card detection.
- Printed calibration card marker detection.
- Manual drag handles for bbox adjustment.
- No-reference centimeter or millimeter measurement.

## Safety

If no trusted reference object is detected, scale returns `needs_reference` and millimeter outputs stay null.

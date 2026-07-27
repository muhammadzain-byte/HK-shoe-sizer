# Foot Measurement Validation Dataset

This folder is for real-device validation of the guided foot measurement system.

Sample rows are examples only. They are not accuracy evidence. Real accuracy must come from real phone photos and manually measured ground truth.

## Folder Structure

- `images/android_chrome/`
- `images/iphone_safari/`
- `images/desktop_webcam/`
- `templates/`
- `reports/`
- `validation_cases.csv`

## Required Real Test Case Data

Each real validation case must include:

1. A real captured image.
2. Manual foot length in millimeters.
3. Manual foot width in millimeters.
4. Reference object type.
5. Reference object bbox or polygon if manually marked.
6. Device and browser info.
7. Capture scenario label.

## Manual Measurement Instructions

- Measure foot length from the longest toe to the back of the heel.
- Measure foot width across the widest forefoot or ball-of-foot area.
- Record measurements in millimeters.
- Measure while the foot is flat on the floor.
- Use the same foot shown in the image.
- Do not enter guessed values.

## Reference Object Defaults

- `credit_card`: 85.60 mm by 53.98 mm.
- `a4_paper`: 210.00 mm by 297.00 mm.
- `calibration_card`: 100.00 mm by 60.00 mm.
- `custom_object`: user must fill width and height manually.

## Reference Object Instructions

- Place the credit card, A4 paper, or calibration card flat beside the foot.
- Keep the object fully visible.
- Keep it on the same floor plane as the foot.
- Do not hold it in hand.
- Do not overlap the foot.
- Avoid heavy perspective tilt.

## Safety Note

Do not claim production accuracy until enough real-device cases pass benchmark thresholds.

The validation harness and sample cases help organize proof. They do not prove accuracy by themselves.

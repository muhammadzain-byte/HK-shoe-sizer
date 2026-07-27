# Measurement Accuracy Validation

Phase 5A adds a validation harness for comparing AI measurements against manual ground truth.

## Script

Run from the project root:

```powershell
python backend\scripts\validate_measurement_accuracy.py --csv datasets\validation\validation_cases.csv --output-dir datasets\validation\reports
```

If `datasets/validation/validation_cases.csv` is missing, the script creates it from the sample/template structure and reports that no accuracy claim can be made.

## CSV Columns

- `image_path`
- `foot_length_mm_ground_truth`
- `foot_width_mm_ground_truth`
- `reference_mode`
- `reference_width_mm`
- `reference_height_mm`
- `reference_bbox_x`
- `reference_bbox_y`
- `reference_bbox_width`
- `reference_bbox_height`
- `notes`

## Outputs

- `artifacts/validation/measurement_accuracy_report.csv`
- `artifacts/validation/measurement_accuracy_summary.json`

## Safety

The harness does not fake measurements. Rows without ground truth or reference-object evidence are excluded from accuracy statistics.

Sample/template cases are not accuracy evidence.

Production accuracy cannot be claimed until enough real-device cases are measured manually and compared.

## External Research Datasets

External datasets are supported under `datasets/external/`, but they are separate from this real-device validation dataset.

The real accuracy dataset remains `datasets/validation/validation_cases.csv`.

External research datasets can help with segmentation, landmarks, masks, normals, and 3D research. They cannot replace real phone images with manual millimeter ground truth.
## Phase 6A Real-Device Benchmarking

Real measurement accuracy evidence now flows through `validation_cases` and `validation_benchmark_results`.
The validation cockpit is for real phone images with manual millimeter ground truth and reference-object evidence.

External datasets under `datasets/external/` and synthetic smoke datasets remain research-only. They must not be used to claim phone measurement accuracy.

Accuracy claims stay blocked until the benchmark summary has at least 50 completed real-device cases, at least 3 device/browser groups, mean length absolute error <= 5 mm, P90 length absolute error <= 8 mm, and scale failure rate <= 10%.

Useful commands:

```powershell
python backend\scripts\run_validation_benchmark.py --status benchmark_ready
python backend\scripts\validate_measurement_accuracy.py --from-db
```

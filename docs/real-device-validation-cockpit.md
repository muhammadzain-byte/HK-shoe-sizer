# Real-Device Validation Cockpit

Phase 6A adds a validation cockpit for real phone capture evidence. It is separate from synthetic and external research datasets.

## What Was Built

- `validation_cases` stores real-device validation case metadata, manual ground truth, reference-object annotation, and scan links.
- `validation_benchmark_results` stores benchmark outputs and error metrics.
- `/api/v1/validation-cases` exposes authenticated case CRUD, scan/upload attachment, benchmark readiness, summaries, and benchmark execution.
- `/validation` provides a frontend cockpit for creating cases, entering manual millimeter ground truth, drawing reference-object bboxes, and running benchmark checks.
- CSV import/export scripts support moving cases between `datasets/validation/validation_cases.csv` and the database.
- Benchmark reports write to `datasets/validation/reports`.

## What Counts As Evidence

A benchmark-ready validation case requires:

- A real uploaded phone image.
- Manual foot length and width in millimeters.
- A linked scan.
- Reference-object or calibration evidence.
- Device/browser/capture scenario metadata where available.

Synthetic masks, smoke datasets, and external research datasets do not count as product accuracy proof.

## Safety Gates

The system does not allow production accuracy claims unless all of these are true:

- At least 50 completed real-device benchmark cases.
- At least 3 device/browser groups.
- Mean length absolute error is <= 5 mm.
- P90 length absolute error is <= 8 mm.
- Scale failure rate is <= 10%.
- Capture rejection behavior is documented.

Even then, the result is internal validation evidence, not a public production claim.

## Commands

```powershell
python backend\scripts\import_validation_cases.py --csv datasets\validation\validation_cases.csv --user-id <USER_UUID>
python backend\scripts\export_validation_cases.py --output datasets\validation\validation_cases_export.csv --user-id <USER_UUID>
python backend\scripts\run_validation_benchmark.py --status benchmark_ready
python backend\scripts\validate_measurement_accuracy.py --from-db
```

Apply migrations before using the DB cockpit:

```powershell
cd backend
alembic upgrade head
```

## Privacy

Foot images and validation telemetry are sensitive biometric-like data. Do not expose cases publicly, do not log raw image bytes, and do not mix user-owned validation cases across accounts.
